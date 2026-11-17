"""Chatbox: answers clinicians' questions about the study.

With ANTHROPIC_API_KEY set, Claude answers using tools that query the study data (patients, verdicts and
evidence, protocol, workflow). Every fact in an answer comes from a tool result, never from the model's
memory. Without a key, a rule-based fallback answers common questions from the same functions.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

import anthropic

from . import state

MODEL = os.getenv("CHATBOX_MODEL", "claude-opus-5-5")

SYSTEM = """You are the study assistant inside Neurovation, a clinical-trial recruitment tool used by clinicians and research coordinators.

Answer questions about the current trial's patients, eligibility, evidence and recruitment workflow.
- Use the tools to look things up. Every fact, number and quote in your answer must come from a tool result.
- Patients have study IDs like PT-101. If someone says "patient 2", they most likely mean PT-102; if rank 2 is a different patient, say which one you used.
- Refer to patients by study ID and to criteria by ID (e.g. I2, E4). Quote evidence sentences exactly when it helps.
- You do not have names, contact details or identifying information, and must not speculate about them. The data custodian can resolve identities in the app.
- This is decision support: you can summarise and suggest, but a clinician decides eligibility and contact.
- Be concise and clinical. Use short paragraphs or bullet points, and tables only for comparing several patients."""

FILTERS = ["all", "to_review", "likely_eligible", "needs_review", "not_eligible", "approved", "information_requested",
           "consent_not_sent", "consent_sent", "consent_obtained", "declined", "enrolled"]

TOOLS = [
    {
        "name": "list_patients",
        "description": "List ranked patients with match score, status, pass/fail/unknown counts, clinician decision and consent status. Use a filter to narrow the list.",
        "input_schema": {"type": "object", "properties": {"filter": {"type": "string", "enum": FILTERS}},
                         "required": ["filter"], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "get_patient",
        "description": "Full screening record for one patient: every criterion's verdict with its evidence sentence, the clinic note, the decision, consent status and activity. Accepts a study ID (PT-102) or a rank number prefixed with 'rank ' (rank 2).",
        "input_schema": {"type": "object", "properties": {"patient": {"type": "string"}}, "required": ["patient"], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "get_protocol",
        "description": "The trial protocol in use: name, matching mode, and the inclusion and exclusion criteria with IDs.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "criterion_summary",
        "description": "For each criterion (or one criterion ID), which patients fail it and which are unknown for it.",
        "input_schema": {"type": "object", "properties": {"criterion_id": {"type": "string", "description": "A criterion ID such as E4, or 'all'"}},
                         "required": ["criterion_id"], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "workflow_summary",
        "description": "Recruitment progress: funnel counts, patients still to review, consent forms outstanding or overdue, enrolments.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
]


# ------------------------------------------------------------------ tool implementations (read-only)
def _rows():
    criteria, results, rows = state.ranking()
    return criteria, results, rows


def _resolve(ref: str) -> str | None:
    _, _, rows = _rows()
    ids = [r["id"] for r in rows]
    ref = ref.strip().upper()
    m = re.match(r"RANK\s*(\d+)", ref)
    if m:
        k = int(m.group(1))
        return next((r["id"] for r in rows if r["rank"] == k), None)
    m = re.search(r"(\d+)", ref)
    if not m:
        return None
    n = int(m.group(1))
    for cand in (f"PT-{n}", f"PT-{100 + n}"):
        if cand in ids:
            return cand
    return None


def _row_summary(r):
    d = state.ss().nv_decisions.get(r["id"])
    p = state.patient(r["id"])
    return {"rank": r["rank"], "id": r["id"], "age": p["age"], "sex": p["sex"], "score": r["score"], "status": r["status"],
            "pass": r["pass"], "fail": r["fail"], "unknown": r["unknown"],
            "decision": state.DECISION_LABEL[d["action"]] if d else "not yet decided",
            "consent": state.consent_label(r["id"]) if d and d["action"] == "approve" else "n/a"}


def list_patients(filter: str = "all"):
    _, _, rows = _rows()
    s = state.ss()
    keep = {
        "all": lambda r: True,
        "to_review": lambda r: r["status"] != "Not eligible" and r["id"] not in s.nv_decisions,
        "likely_eligible": lambda r: r["status"] == "Likely eligible",
        "needs_review": lambda r: r["status"] == "Needs review",
        "not_eligible": lambda r: r["status"] == "Not eligible",
        "approved": lambda r: s.nv_decisions.get(r["id"], {}).get("action") == "approve",
        "information_requested": lambda r: s.nv_decisions.get(r["id"], {}).get("action") == "request_info",
        "consent_not_sent": lambda r: r["id"] in state.approved() and state.consent_label(r["id"]) == "Not sent",
        "consent_sent": lambda r: state.consent_label(r["id"]) == "Sent",
        "consent_obtained": lambda r: state.consent_label(r["id"]) in ("Consent obtained", "Enrolled"),
        "declined": lambda r: state.consent_label(r["id"]) == "Declined",
        "enrolled": lambda r: state.consent_label(r["id"]) == "Enrolled",
    }.get(filter, lambda r: True)
    out = [_row_summary(r) for r in rows if keep(r)]
    return {"filter": filter, "count": len(out), "patients": out}


def get_patient(patient: str):
    pid = _resolve(patient)
    if not pid:
        return {"error": f"No patient matches '{patient}'. Study IDs run PT-101 to PT-120."}
    criteria, results, rows = _rows()
    r = next(x for x in rows if x["id"] == pid)
    by = {x["id"]: x for x in results[pid]}
    c = state.consent(pid)
    return {
        **_row_summary(r),
        "criteria": [{"id": k["id"], "type": k["type"], "criterion": k["text"], "verdict": by.get(k["id"], {}).get("verdict", "unknown"),
                      "evidence": by.get(k["id"], {}).get("evidence", "")} for k in criteria],
        "clinic_note": state.patient(pid)["note"],
        "consent_detail": {k: (v.isoformat(timespec="minutes") if isinstance(v, datetime) else v) for k, v in c.items()},
        "activity": [f"{e['time']:%H:%M} {e['action']} ({e['role']}) {e['detail']}" for e in state.ss().nv_log if e["pid"] == pid][:10],
    }


def get_protocol():
    s = state.ss()
    return {"protocol": state.protocol_name(), "source_file": s.source, "matching_mode": s.results_mode, "criteria": s.current}


def criterion_summary(criterion_id: str = "all"):
    criteria, results, _ = _rows()
    out = []
    for c in criteria:
        if criterion_id.lower() != "all" and c["id"].upper() != criterion_id.upper():
            continue
        out.append({"id": c["id"], "type": c["type"], "criterion": c["text"],
                    "fail": [p for p, rs in results.items() if any(x["id"] == c["id"] and x["verdict"] == "fail" for x in rs)],
                    "unknown": [p for p, rs in results.items() if any(x["id"] == c["id"] and x["verdict"] == "unknown" for x in rs)]})
    return {"criteria": out} if out else {"error": f"No criterion '{criterion_id}'."}


def workflow_summary():
    s = state.ss()
    _, _, rows = _rows()
    appr = state.approved()
    labels = {p: state.consent_label(p) for p in appr}
    overdue = [p for p, c in s.nv_consent.items() if c.get("status") == "sent" and (datetime.now() - c["sent_at"]).days > 7]
    return {
        "screened": len(rows),
        "by_status": {k: sum(r["status"] == k for r in rows) for k in ("Likely eligible", "Needs review", "Not eligible")},
        "to_review": [r["id"] for r in rows if r["status"] != "Not eligible" and r["id"] not in s.nv_decisions],
        "approved": appr,
        "information_requested": [p for p, d in s.nv_decisions.items() if d["action"] == "request_info"],
        "consent": {lab: [p for p, v in labels.items() if v == lab] for lab in ("Not sent", "Sent", "Consent obtained", "Declined", "Enrolled")},
        "consent_overdue_over_7_days": overdue,
    }


FUNCS = {"list_patients": list_patients, "get_patient": get_patient, "get_protocol": get_protocol,
         "criterion_summary": criterion_summary, "workflow_summary": workflow_summary}


def run_tool(name: str, args: dict) -> str:
    fn = FUNCS.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool {name}"})
    return json.dumps(fn(**(args or {})), default=str)


# ------------------------------------------------------------------ Claude
def ask_claude(client: anthropic.Anthropic, history: list, question: str):
    """Run one user turn through Claude with tools. Mutates `history`. Returns (answer_text, tools_used)."""
    history.append({"role": "user", "content": question})
    used = []
    for _ in range(8):
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            messages=history,
            output_config={"effort": "low"},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        history.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            return "I can't help with that request.", used
        if resp.stop_reason == "pause_turn":
            continue
        calls = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not calls:
            text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
            if resp.stop_reason == "max_tokens":
                text += "\n\n(Answer cut short.)"
            return text or "(No answer.)", used
        results = []
        for b in calls:
            used.append(b.name)
            try:
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": run_tool(b.name, b.input)})
            except Exception as exc:  # report tool failures to the model instead of crashing the chat
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Error: {exc}", "is_error": True})
        history.append({"role": "user", "content": results})
    return "Sorry, that took too many steps. Please ask a narrower question.", used


# ------------------------------------------------------------------ offline fallback
def _fmt_patient(d):
    lines = [f"**{d['id']}** (rank {d['rank']}, {d['age']} y {d['sex']}): **{d['status']}**, match score {d['score']:.2f} "
             f"({d['pass']} pass, {d['fail']} fail, {d['unknown']} unknown). Decision: {d['decision']}."]
    gaps = [c for c in d["criteria"] if c["verdict"] != "pass"]
    if gaps:
        lines.append("")
        for c in gaps:
            ev = f' “{c["evidence"]}”' if c["evidence"] else " Not stated in the note."
            lines.append(f"- {c['id']} {c['criterion']}: **{c['verdict']}**.{ev}")
    else:
        lines.append("Every criterion passes.")
    if d["consent"] != "n/a":
        lines.append(f"\nConsent: {d['consent']}.")
    return "\n".join(lines)


def ask_offline(question: str) -> str:
    q = question.lower()
    if re.search(r"\b(names?|phone|address|email|nric|contact details?|identity)\b", q):
        return "I don't have names or contact details. Study data uses IDs only; the data custodian can see contact details on the Consent page."
    m = re.search(r"\b(?:pt[- ]?\d+|patient\s*#?\s*\d+|rank\s*\d+|\b1[01]\d\b)", q)
    if m:
        ref = m.group(0)
        d = get_patient("rank " + re.search(r"\d+", ref).group(0) if ref.startswith("rank") else ref)
        if "error" in d:
            return d["error"]
        note = ""
        num = re.search(r"\d+", ref).group(0)
        if ref.startswith("patient") and int(num) < 100:
            note = f"(Reading “{ref}” as {d['id']}; ask for “rank {num}” for the patient ranked there.)\n\n"
        return note + _fmt_patient(d)
    if re.search(r"one (criterion|item) short|almost|nearly|close to", q):
        near = [r for r in list_patients("all")["patients"] if r["fail"] == 0 and r["unknown"] == 1]
        if not near:
            return "No patient is exactly one unknown criterion away from Likely eligible."
        out = []
        for r in near:
            d = get_patient(r["id"])
            gap = next(c for c in d["criteria"] if c["verdict"] == "unknown")
            out.append(f"- **{r['id']}** (rank {r['rank']}): {gap['id']} {gap['criterion']} is not stated in the note.")
        return f"{len(near)} patients pass everything except one unknown item:\n" + "\n".join(out)
    if re.search(r"exclud|fail|why not|barrier|reason", q):
        cs = sorted(criterion_summary("all")["criteria"], key=lambda c: -len(c["fail"]))
        top = [c for c in cs if c["fail"]][:4]
        return "Most common reasons patients are excluded:\n" + "\n".join(f"- **{c['id']}** {c['criterion']}: {len(c['fail'])} ({', '.join(c['fail'])})" for c in top)
    if re.search(r"unknown|missing|not stated|gap", q):
        cs = sorted(criterion_summary("all")["criteria"], key=lambda c: -len(c["unknown"]))
        top = [c for c in cs if c["unknown"]][:4]
        return "Most often not stated in the notes:\n" + "\n".join(f"- **{c['id']}** {c['criterion']}: {len(c['unknown'])} ({', '.join(c['unknown'])})" for c in top)
    if re.search(r"consent|overdue|follow.?up|enrol|progress|summary|status|how many", q):
        w = workflow_summary()
        c = w["consent"]
        return (f"{w['screened']} screened: {w['by_status']['Likely eligible']} likely eligible, {w['by_status']['Needs review']} need review, "
                f"{w['by_status']['Not eligible']} not eligible. {len(w['to_review'])} still to review; {len(w['approved'])} approved for contact.\n\n"
                f"Consent: {len(c['Not sent'])} not sent, {len(c['Sent'])} awaiting reply"
                f"{' (overdue: ' + ', '.join(w['consent_overdue_over_7_days']) + ')' if w['consent_overdue_over_7_days'] else ''}, "
                f"{len(c['Consent obtained'])} obtained, {len(c['Declined'])} declined, {len(c['Enrolled'])} enrolled.")
    if re.search(r"eligible|best|top|who should|contact first|candidates|rank", q):
        top = [r for r in list_patients("all")["patients"] if r["status"] != "Not eligible"][:6]
        return "Strongest candidates, in rank order:\n" + "\n".join(
            f"- **{r['id']}** · {r['status']} · score {r['score']:.2f} · {r['unknown']} unknown · {r['decision']}" for r in top)
    if re.search(r"criteri|inclusion|exclusion|protocol", q):
        p = get_protocol()
        return f"**{p['protocol']}**\n" + "\n".join(f"- **{c['id']}** ({c['type']}) {c['text']}" for c in p["criteria"])
    return ("I can look up any patient (e.g. “PT-104” or “patient 4”), the strongest candidates, why patients are excluded, what the notes "
            "don't say, who is one item short, the protocol criteria, or consent and enrolment progress. "
            "Add an ANTHROPIC_API_KEY to the app's secrets for free-form questions.")
