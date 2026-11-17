"""Grounded study assistant: answers only from the criteria, matching results and workflow records.

Offline and deterministic: each question is matched to a query function, and every number in the
answer comes from that query. A live version would let an LLM choose the query ("tool use"), but the
numbers would still come from the same functions.
"""
import re
from datetime import datetime

from . import state

SUGGESTIONS = [
    "Which patients are one criterion short?",
    "Which criterion excludes the most patients?",
    "Who is overdue for a consent follow-up?",
    "How many patients are enrolled?",
    "What is the cognitive cut-off in this protocol?",
]


def answer(q: str):
    """Return (text, sources, refused)."""
    s = q.lower()
    ss = state._ss()
    criteria, results, rows, source = state.ranked()
    by_id = {c["id"]: c for c in criteria}

    if re.search(r"\b(name|address|phone|nric|mrn|identity|who is pt)\b", s):
        if ss.nv_role != "Data custodian":
            return (f"Your role ({ss.nv_role}) cannot see identifying information; study data uses IDs only. "
                    "A data custodian can resolve an ID in the identity vault, and each look-up is logged.", ["Access policy"], True)
        return ("Identity look-ups are done one at a time in the identity vault (Consent and onboarding page), so each is logged.", ["Access policy"], False)

    m = re.search(r"pt-\d+", s)
    if m:
        pid = m.group(0).upper()
        r = next((x for x in rows if x["id"] == pid), None)
        if not r:
            return (f"{pid} is not in the study database.", ["Study database"], False)
        gaps = [x for x in results[pid] if x["verdict"] != "pass"]
        lines = [f'• {x["id"]} {by_id[x["id"]]["text"]}: {x["verdict"]}' + (f' (“{x["evidence"]}”)' if x["evidence"] else "") for x in gaps]
        return (f'{pid} is ranked {r["rank"]} of {len(rows)} with score {r["score"]:.2f} ({r["status"]}).'
                + ("\n" + "\n".join(lines) if lines else " Every criterion passes."), [f"Matching results · {pid}", source], False)

    if re.search(r"one criterion|one short|almost|nearly", s):
        near = [r for r in rows if r["fail"] == 0 and r["unknown"] == 1]
        if not near:
            return ("No patient has exactly one unknown criterion and no fails.", ["Matching results"], False)
        detail = []
        for r in near:
            x = next(x for x in results[r["id"]] if x["verdict"] == "unknown")
            detail.append(f'{r["id"]} (missing {x["id"]}: {by_id[x["id"]]["text"]})')
        return (f"{len(near)} patients pass everything except one unknown item: " + "; ".join(detail) + ".", ["Matching results", source], False)

    if re.search(r"exclud|screen fail|most fail|barrier", s):
        counts = {}
        for rs in results.values():
            for x in rs:
                if x["verdict"] == "fail":
                    counts[x["id"]] = counts.get(x["id"], 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        if not top:
            return ("No patient fails any criterion.", ["Matching results"], False)
        return ("Most common reasons for exclusion: " + "; ".join(f'{cid} {by_id[cid]["text"]} ({n} patients)' for cid, n in top) + ". A patient can fail more than one.",
                ["Matching results"] + [f"Criterion {cid}" for cid, _ in top], False)

    if re.search(r"overdue|follow.?up|unsigned|waiting", s):
        late = [(p, (datetime.now() - datetime.strptime(c["invited_at"], "%Y-%m-%d")).days) for p, c in ss.nv_consent.items()
                if c.get("invited_at") and not c.get("signed_at")]
        late = [(p, d) for p, d in late if d > 7]
        if not late:
            return ("No consent invitation has been unsigned for more than 7 days.", ["Consent register"], False)
        return ("Unsigned for more than 7 days: " + ", ".join(f"{p} ({d} days)" for p, d in late) + ".", ["Consent register"], False)

    if re.search(r"enrol|how many|progress|consent", s):
        st_ = {r["id"]: state.stage_of(r["id"], r["status"]) for r in rows}
        n = lambda k: sum(1 for v in st_.values() if v == k)
        return (f'{n("Enrolled")} enrolled, {n("Consented")} consented and awaiting baseline, {n("Invited")} invited, '
                f'{n("Approved for contact")} approved but not yet invited.', ["Consent register", "Decision log"], False)

    if re.search(r"cognit|mmse|moca|dementia", s):
        hits = [c for c in criteria if re.search(r"mental|mmse|moca|cognit|dementia", c["text"], re.I)]
        if hits:
            return ("\n".join(f'{c["id"]} ({c["type"]}): “{c["text"]}”' for c in hits), ["Protocol criteria"], False)
        return ("This protocol has no cognitive criterion.", ["Protocol criteria"], False)

    if re.search(r"criteria|inclusion|exclusion|eligib", s):
        return ("\n".join(f'{c["id"]} ({c["type"]}): {c["text"]}' for c in criteria), ["Protocol criteria"], False)

    return ("I only answer from the protocol, the matching results and the study records. Try asking about patients who are "
            "one criterion short, the most common exclusions, overdue consent, enrolment, a criterion, or a patient ID such as PT-101.", [], False)
