"""Dashboard: where recruitment stands and where it stalls. Every number and bar leads to the patients behind it."""
import html
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from neurovation import state, ui

ss = state.ss()
if not state.matched():
    st.warning("Submit a protocol first.", icon=":material/lock:")
    st.stop()

criteria, results, rows = state.ranking()
by_crit = {c["id"]: c for c in criteria}
ui.header("Dashboard", "Where recruitment stands and where it stalls. Click any number, bar or patient to go straight to it.",
          [state.protocol_name(), "Dashboard"])


def go_screening(view="All", pid=None):
    ss.nv_filter_req = view
    if pid:
        ss.nv_selected = pid
    st.switch_page("views/screening.py")


def patient_buttons(pids, prefix, page="views/screening.py", n=4):
    if not pids:
        st.caption("None.")
        return
    cols = st.columns(n)
    for i, pid in enumerate(pids):
        if cols[i % n].button(pid, key=f"{prefix}_{pid}", width="stretch"):
            ui.open_patient(pid, page)


# ---------------------------------------------------------------- headline numbers (clickable)
labels = {p: state.consent_label(p) for p in state.approved()}
stage = {
    "Screened": [r["id"] for r in rows],
    "Not ruled out": [r["id"] for r in rows if r["status"] != "Not eligible"],
    "Approved for contact": state.approved(),
    "Consent form sent": [p for p, v in labels.items() if v != "Not sent"],
    "Consent obtained": [p for p, v in labels.items() if v in ("Consent obtained", "Enrolled")],
    "Enrolled": [p for p, v in labels.items() if v == "Enrolled"],
}
targets = {
    "Screened": lambda: go_screening("All"), "Not ruled out": lambda: go_screening("To review"),
    "Approved for contact": lambda: st.switch_page("views/consent.py"), "Consent form sent": lambda: st.switch_page("views/consent.py"),
    "Consent obtained": lambda: st.switch_page("views/consent.py"), "Enrolled": lambda: st.switch_page("views/consent.py"),
}
cols = st.columns(len(stage))
for col, (lab, ps) in zip(cols, stage.items()):
    with col.container(border=True):
        st.metric(lab, len(ps))
        if st.button("Open", key=f"kpi_{lab}", type="tertiary", icon=":material/arrow_forward:"):
            targets[lab]()

AX = dict(labelColor="#667085", titleColor="#667085", gridColor="#E4E7EC", domainColor="#E4E7EC", labelFont="Inter", labelFontSize=12)

left, right = st.columns([1.3, 1], gap="large")
with left:
    with st.container(border=True):
        st.markdown("**Recruitment funnel** <span class='nv-muted'>· click a bar to list those patients</span>", unsafe_allow_html=True)
        df = pd.DataFrame([{"stage": k, "n": len(v), "order": i} for i, (k, v) in enumerate(stage.items())])
        sel = alt.selection_point(name="stage", fields=["stage"])
        chart = (alt.Chart(df).mark_bar(cornerRadiusEnd=3, height=20)
                 .encode(x=alt.X("n:Q", title=None, axis=alt.Axis(tickMinStep=1, **AX)),
                         y=alt.Y("stage:N", sort=alt.SortField("order"), title=None, axis=alt.Axis(labelLimit=220, **AX)),
                         color=alt.condition(sel, alt.value(ui.PRIMARY), alt.value("#C5D4F6")), tooltip=["stage", "n"])
                 .add_params(sel).properties(height=240).configure_view(strokeWidth=0))
        ev = st.altair_chart(chart, on_select="rerun", key="funnel", width="stretch")
        picked = (ev.selection.get("stage") or [{}])[0].get("stage") if ev and ev.selection else None
        if picked:
            st.markdown(f"**{picked}** · {len(stage[picked])} patients")
            patient_buttons(stage[picked], "fun", "views/consent.py" if picked in list(stage)[3:] else "views/screening.py", n=6)

with right:
    with st.container(border=True):
        st.markdown("**Needs attention**")
        overdue = [p for p, c in ss.nv_consent.items() if c.get("status") == "sent" and (datetime.now() - c["sent_at"]).days > 7]
        items = [
            ("Patients still to review", [r["id"] for r in rows if r["status"] != "Not eligible" and r["id"] not in ss.nv_decisions], "views/screening.py", "blue"),
            ("Information requested", [p for p, d in ss.nv_decisions.items() if d["action"] == "request_info"], "views/screening.py", "warn"),
            ("Approved, consent not sent", [p for p, v in labels.items() if v == "Not sent"], "views/consent.py", "warn"),
            ("Consent form unanswered for over 7 days", overdue, "views/consent.py", "bad"),
            ("Consent obtained, not yet enrolled", [p for p, v in labels.items() if v == "Consent obtained"], "views/consent.py", "ok"),
        ]
        for i, (lab, ps, page, tone) in enumerate(items):
            with st.expander(f"{lab} · {len(ps)}", expanded=bool(ps) and i == 0):
                patient_buttons(ps, f"att{i}", page)

# ---------------------------------------------------------------- criteria (clickable)
fails, unknowns = {}, {}
for pid, rs in results.items():
    for r in rs:
        target = fails if r["verdict"] == "fail" else unknowns if r["verdict"] == "unknown" else None
        if target is not None:
            target.setdefault(r["id"], []).append(pid)


def crit_chart(data, color, key, title):
    df = pd.DataFrame([{"id": cid, "label": f"{cid} · {by_crit[cid]['text'][:46]}{'…' if len(by_crit[cid]['text']) > 46 else ''}", "n": len(ps)}
                       for cid, ps in data.items() if cid in by_crit])
    with st.container(border=True):
        st.markdown(f"**{title}** <span class='nv-muted'>· click a bar to list patients</span>", unsafe_allow_html=True)
        if df.empty:
            st.caption("None.")
            return
        sel = alt.selection_point(name="crit", fields=["id"])
        ch = (alt.Chart(df).mark_bar(cornerRadiusEnd=3, height=14)
              .encode(x=alt.X("n:Q", title=None, axis=alt.Axis(tickMinStep=1, **AX)),
                      y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=330, **AX)),
                      color=alt.condition(sel, alt.value(color), alt.value("#E4E7EC")), tooltip=["label", "n"])
              .add_params(sel).properties(height=max(140, 30 * len(df))).configure_view(strokeWidth=0))
        ev = st.altair_chart(ch, on_select="rerun", key=key, width="stretch")
        cid = (ev.selection.get("crit") or [{}])[0].get("id") if ev and ev.selection else None
        if cid:
            st.markdown(f"**{cid}** · {html.escape(by_crit[cid]['text'])}")
            patient_buttons(data[cid], f"{key}_p")


c1, c2 = st.columns(2, gap="large")
with c1:
    crit_chart(fails, "#B42318", "fails", "Why patients are excluded")
with c2:
    crit_chart(unknowns, "#B54708", "unknowns", "What the notes don't say")

# ---------------------------------------------------------------- activity
with st.container(border=True):
    st.markdown("**Recent activity**")
    events = [e for e in ss.nv_log if e["action"] != "Switched role"][:10]
    if not events:
        st.caption("No activity yet.")
    for i, e in enumerate(events):
        a, b, c = st.columns([5, 1.2, 1], vertical_alignment="center")
        a.markdown(f"**{html.escape(e['action'])}** <span class='nv-muted'>{state.ROLE_NAMES[e['role']]}"
                   f"{' · ' + html.escape(e['detail']) if e['detail'] else ''}</span>", unsafe_allow_html=True)
        if e["pid"] and b.button(e["pid"], key=f"act_{i}", type="tertiary"):
            ui.open_patient(e["pid"])
        c.markdown(f"<span class='nv-muted'>{e['time']:%H:%M}</span>", unsafe_allow_html=True)
