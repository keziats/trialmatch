"""Step 2 · Screening: ranked patients, evidence, and the clinician's decision on one page.

Replaces the original 'Ranked patients' and 'Evidence' tabs and the separate review page, which showed
the same information three times. Ranking, score and status come from trialmatch.scoring, unchanged.
"""
import html

import streamlit as st

from neurovation import state, ui
from neurovation.patient_table import patient_table
from trialmatch import scoring as S

ss = state.ss()
if not state.matched():
    st.warning("Submit a protocol first.", icon=":material/lock:")
    if st.button("Go to protocol matching"):
        st.switch_page("views/protocol.py")
    st.stop()

criteria, results, rows = state.ranking()
patients = {p["id"]: p for p in state.load_patients()}
by_crit = {c["id"]: c for c in criteria}
is_pi = ss.nv_role == "Principal investigator"

ui.header(
    "Screening",
    "Patients ranked by match score. <b>Hover</b> over a patient to preview the evidence, or over a Pass / Fail / Unknown count "
    "to see just those criteria. <b>Click</b> a patient to open the full record and decide.",
    [state.protocol_name(), "2 · Screening"],
)

# ---------------------------------------------------------------- summary + filter
counts = {
    "All": len(rows),
    "To review": sum(1 for r in rows if r["status"] != "Not eligible" and r["id"] not in ss.nv_decisions),
    "Likely eligible": sum(r["status"] == "Likely eligible" for r in rows),
    "Needs review": sum(r["status"] == "Needs review" for r in rows),
    "Not eligible": sum(r["status"] == "Not eligible" for r in rows),
    "Decided": len(ss.nv_decisions),
}
ss.setdefault("nv_filter", "All")
if ss.get("nv_filter_req"):  # set by links elsewhere (e.g. the dashboard)
    ss.nv_filter = ss.pop("nv_filter_req")
view = st.segmented_control("Show", list(counts), format_func=lambda k: f"{k} · {counts[k]}", key="nv_filter", label_visibility="collapsed") or "All"


def keep(r):
    if view == "All":
        return True
    if view == "To review":
        return r["status"] != "Not eligible" and r["id"] not in ss.nv_decisions
    if view == "Decided":
        return r["id"] in ss.nv_decisions
    return r["status"] == view


shown = [r for r in rows if keep(r)]
order = [r["id"] for r in rows]


def next_to_review(after: str):
    queue = [r["id"] for r in rows if r["status"] != "Not eligible" and r["id"] not in ss.nv_decisions]
    later = [p for p in queue if order.index(p) > order.index(after)]
    return (later or queue or [None])[0]


if ss.nv_selected not in patients:
    ss.nv_selected = (shown or rows)[0]["id"]

left, right = st.columns([1.8, 1], gap="medium")
with left:
    if not shown:
        st.info("No patients in this view.", icon=":material/filter_alt_off:")
    else:
        clicked = patient_table(shown, results, criteria, patients, ss.nv_decisions, ss.nv_selected)
        if clicked and clicked != ss.nv_selected:
            ss.nv_selected = clicked
            st.rerun()
    st.caption(f"Score = (passes + 0.5 × unknowns) ÷ criteria, halved for each fail. It orders the review queue; a clinician decides. "
               f"Results: {ss.results_mode}.")

# ---------------------------------------------------------------- patient record
pid = ss.nv_selected
row = next(r for r in rows if r["id"] == pid)
p = patients[pid]
res = {r["id"]: r for r in results[pid]}
dec = ss.nv_decisions.get(pid)

with right:
    with st.container(border=True):
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
            f'<span style="font-size:18px;font-weight:600;color:{ui.INK};font-family:IBM Plex Mono,monospace">{html.escape(pid)}</span>'
            f'<span>{ui.badge(row["status"], ui.STATUS_TONE[row["status"]])}</span></div>'
            f'<div class="nv-muted">Rank {row["rank"]} of {len(rows)} · {p["age"]} years · {"female" if p["sex"] == "F" else "male"}</div>'
            f'<div class="nv-kv"><div>Match score<b>{row["score"]:.2f}</b></div>'
            f'<div>Pass · Fail · Unk.<b>{row["pass"]} · {row["fail"]} · {row["unknown"]}</b></div>'
            f'<div>Decision<b>{state.DECISION_LABEL[dec["action"]] if dec else "Not yet"}</b></div></div>',
            unsafe_allow_html=True,
        )

        # ---- decision bar
        if dec:
            st.markdown(ui.badge(f'{state.DECISION_LABEL[dec["action"]]} by {state.ROLE_NAMES[dec["by"]]} · {dec["at"]:%d %b %H:%M}',
                                 ui.DECISION_TONE[dec["action"]]) + (f' <span class="nv-muted">“{html.escape(dec["note"])}”</span>' if dec["note"] else ""),
                        unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if b1.button("Change decision", icon=":material/undo:", width="stretch"):
                state.undo_decision(pid)
                st.rerun()
            nxt = next_to_review(pid)
            if b2.button("Next to review", icon=":material/arrow_downward:", width="stretch", disabled=not nxt):
                ss.nv_selected = nxt
                st.rerun()
        else:
            note = st.text_input("Note (optional)", key=f"note_{pid}", placeholder="e.g. confirm MRI date at next visit", label_visibility="collapsed")

            def act(action):
                state.decide(pid, action, st.session_state.get(f"note_{pid}", ""))
                st.toast(f"{pid}: {state.DECISION_LABEL[action].lower()}", icon=":material/check:")
                ss.nv_selected = next_to_review(pid) or pid

            st.button("Approve for contact", type="primary", icon=":material/check:", width="stretch", on_click=act, args=("approve",),
                      disabled=not is_pi or row["status"] == "Not eligible",
                      help="Approve for contact" if is_pi else "Only the principal investigator can approve (switch role in the sidebar)")
            b2, b3 = st.columns(2)
            b2.button("Need more info", icon=":material/help:", width="stretch", on_click=act, args=("request_info",),
                      help="Ask the team to confirm missing items")
            b3.button("Not eligible", icon=":material/close:", width="stretch", on_click=act, args=("reject",))
            if not is_pi:
                st.caption("Approval is for the principal investigator. Switch role in the sidebar.")
            elif row["status"] == "Not eligible":
                st.caption("At least one criterion fails, so this patient cannot be approved. Check the evidence below.")

        # ---- evidence
        t1, t2, t3 = st.tabs(["Criteria", "Clinic note", "Activity"])
        with t1:
            items = []
            for c in criteria:
                r = res.get(c["id"], {"verdict": "unknown", "evidence": ""})
                ev = (f'<div class="nv-quote">“{html.escape(r["evidence"])}”</div>' if r.get("evidence")
                      else '<div class="nv-muted">Not stated in the note.</div>')
                items.append(
                    f'<div class="nv-crit">{ui.verdict_icon(r["verdict"])}<div>'
                    f'<div style="display:flex;justify-content:space-between;gap:8px"><span><b>{c["id"]}</b> '
                    f'<span class="nv-muted">{c["type"]}</span> · {html.escape(c["text"])}</span>'
                    f'{ui.badge(ui.VERDICT_LABEL[r["verdict"]], ui.VERDICT_TONE[r["verdict"]])}</div>{ev}</div></div>'
                )
            st.markdown("".join(items), unsafe_allow_html=True)
        with t2:
            st.markdown(f'<div class="nv-note">{ui.highlight_note(p["note"], results[pid])}</div>', unsafe_allow_html=True)
            st.caption("Highlights: green = pass, red = fail, amber = unknown. Hover a highlight to see which criterion it supports.")
        with t3:
            events = [e for e in ss.nv_log if e["pid"] == pid]
            if not events:
                st.caption("No activity yet.")
            for e in events:
                st.markdown(f'<div class="nv-row"><span><b>{html.escape(e["action"])}</b> '
                            f'<span class="nv-muted">{state.ROLE_NAMES[e["role"]]}{" · " + html.escape(e["detail"]) if e["detail"] else ""}</span></span>'
                            f'<span class="nv-muted">{e["time"]:%H:%M}</span></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- footer
st.divider()
f1, f2 = st.columns([3, 1])
n_appr = len(state.approved())
f1.markdown(f"**{n_appr}** approved for contact · **{counts['To review']}** still to review")
if f2.button("Continue to consent", type="primary", icon=":material/arrow_forward:", width="stretch", disabled=n_appr == 0,
             help=None if n_appr else "Approve at least one patient first"):
    st.switch_page("views/consent.py")

# Kezia's check of live AI matching against the synthetic correct answers (only meaningful in Live mode)
if ss.results_mode.startswith("Live") and [c["id"] for c in criteria] == [c["id"] for c in state.load_sample_criteria()]:
    with st.expander("Check Claude against the synthetic ground truth"):
        cmp = S.compare({q["id"]: q["truth"] for q in state.load_patients()}, results)
        c1, c2, c3 = st.columns(3)
        c1.metric("Criterion-level agreement", f"{cmp['criterion_agreement']:.0%}")
        rec, prec = cmp["recall_of_possible_eligibles"], cmp["precision_of_possible_eligibles"]
        c2.metric("Recall of possible eligibles", "n/a" if rec is None else f"{rec:.0%}")
        c3.metric("Precision", "n/a" if prec is None else f"{prec:.0%}")
        st.caption("A patient counts as 'possible eligible' when no criterion is Fail. Recall is the number to watch: a missed patient never hears about the trial.")
