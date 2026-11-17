"""Step 3 · Consent: send consent forms (one, several or all), track replies, record paper consent, enrol."""
import html

import streamlit as st

from neurovation import state, ui

ss = state.ss()
if not state.matched():
    st.warning("Submit a protocol first.", icon=":material/lock:")
    st.stop()

criteria, results, rows = state.ranking()
rank = {r["id"]: r for r in rows}
pids = sorted(state.approved(), key=lambda p: rank[p]["rank"])

ui.header(
    "Consent",
    "Patients approved for contact. Send the electronic consent form to one patient, a selection, or everyone at once. "
    "If a patient signs on paper, scan the form and review it here.",
    [state.protocol_name(), "3 · Consent"],
)

if not pids:
    st.info("No patients approved for contact yet. Approve patients on the Screening page first.", icon=":material/info:")
    if st.button("Go to screening", icon=":material/arrow_back:"):
        st.switch_page("views/screening.py")
    st.stop()

labels = {p: state.consent_label(p) for p in pids}
count = lambda lab: sum(1 for v in labels.values() if v == lab)
m = st.columns(5)
for col, (lab, n) in zip(m, [("Approved", len(pids)), ("Awaiting reply", count("Sent")), ("Consent obtained", count("Consent obtained") + count("Enrolled")),
                             ("Declined", count("Declined")), ("Enrolled", count("Enrolled"))]):
    with col.container(border=True):
        st.metric(lab, n)


# ---------------------------------------------------------------- participant view (e-consent) dialog
@st.dialog("Electronic consent · participant view", width="large")
def participant_view(pid):
    st.caption(f"What {pid} sees after opening the secure link. Five True / False questions check understanding before signature.")
    questions = [
        ("Taking part may mean brain surgery to implant a stimulator, or continuing best medical therapy.", True),
        ("You can leave the study at any time without it affecting your usual care.", True),
        ("Joining the study is required to keep seeing your neurologist.", False),
        ("Your study data is stored under a study ID, not your name.", True),
        ("You must stop all Parkinson's medication before joining.", False),
    ]
    answers = [st.radio(f"{i + 1}. {q}", ["True", "False"], index=None, horizontal=True, key=f"cq_{pid}_{i}") for i, (q, _) in enumerate(questions)]
    signed = st.checkbox("I have read the information sheet and agree to take part.", key=f"csign_{pid}")
    if st.button("Sign and submit", type="primary", disabled=None in answers or not signed):
        score = sum((a == "True") == truth for a, (_, truth) in zip(answers, questions))
        if score < 4:
            state.log("Comprehension below 4/5", pid, f"{score}/5; call-back before signature")
            st.warning(f"Comprehension {score}/5. The study team will call to explain again before signature.")
        else:
            state.record_consent(pid, "econsent", comprehension=score)
            st.rerun()


# ---------------------------------------------------------------- bulk actions
not_sent = [p for p in pids if labels[p] == "Not sent"]
selected = [p for p in pids if ss.get(f"pick_{p}")]


def select_all():
    for p in pids:
        ss[f"pick_{p}"] = ss.pick_all


a1, a2, a3, a4 = st.columns([1.2, 1.4, 1.4, 1.4])
a1.checkbox("Select all", key="pick_all", on_change=select_all)
if a2.button(f"Send to selected ({len(selected)})", icon=":material/send:", disabled=not selected, width="stretch"):
    state.send_consent(selected)
    for p in selected:
        ss[f"pick_{p}"] = False
    st.toast(f"Consent form sent to {len(selected)} patient{'s' if len(selected) > 1 else ''}", icon=":material/mark_email_read:")
    st.rerun()
if a3.button(f"Send to all not yet sent ({len(not_sent)})", type="primary", icon=":material/forward_to_inbox:", disabled=not not_sent, width="stretch"):
    state.send_consent(not_sent)
    st.toast(f"Consent form sent to {len(not_sent)} patients", icon=":material/mark_email_read:")
    st.rerun()
if a4.button("Simulate replies (demo)", icon=":material/science:", disabled=not count("Sent"), width="stretch",
             help="Fill in synthetic participant replies for forms already sent"):
    state.simulate_replies()
    st.rerun()

# ---------------------------------------------------------------- register
WIDTHS = [0.35, 0.5, 0.9, 1.15, 1.7, 1.75, 1.35]
with st.container(border=True):
    h = st.columns(WIDTHS, vertical_alignment="center")
    for col, t in zip(h, ["", "Rank", "Patient", "Screening", "Contact" + ("" if state.can_reveal() else " (masked)"), "Consent", "Action"]):
        col.markdown(f'<span class="nv-muted">{t}</span>', unsafe_allow_html=True)
    for pid in pids:
        c, r, lab = state.consent(pid), rank[pid], labels[pid]
        info = state.contact(pid)
        cols = st.columns(WIDTHS, vertical_alignment="center")
        cols[0].checkbox("select", key=f"pick_{pid}", label_visibility="collapsed")
        cols[1].markdown(f"{r['rank']}")
        if cols[2].button(pid, key=f"open_{pid}", type="tertiary", help="Open screening record"):
            ui.open_patient(pid)
        cols[3].markdown(ui.badge(r["status"], ui.STATUS_TONE[r["status"]]), unsafe_allow_html=True)
        phone, email = (info["phone"], info["email"]) if state.can_reveal() else (info["phone_masked"], info["email_masked"])
        cols[4].markdown(f'<div style="font-size:13px;line-height:1.35">{phone}<br><span class="nv-muted">{email}</span></div>', unsafe_allow_html=True)
        detail = ""
        if lab == "Sent":
            days = (state.datetime.now() - c["sent_at"]).days
            detail = f"sent {c['sent_at']:%d %b}" + (f" · {days} d, follow up" if days > 7 else "")
        elif lab in ("Consent obtained", "Enrolled"):
            detail = f"{'paper, scan reviewed' if c.get('channel') == 'paper' else 'e-consent'} · {c.get('study_id', '')}"
        elif lab == "Declined":
            detail = f"{c['declined_at']:%d %b}"
        tone = "bad" if lab == "Sent" and "follow up" in detail else ui.CONSENT_TONE[lab]
        cols[5].markdown(ui.badge(lab, tone) + (f'<div class="nv-muted" style="margin-top:3px">{html.escape(detail)}</div>' if detail else ""),
                         unsafe_allow_html=True)
        with cols[6]:
            b, menu = st.columns([3, 1], vertical_alignment="center")
            if lab == "Not sent":
                if b.button("Send", key=f"send_{pid}", icon=":material/send:", width="stretch"):
                    state.send_consent([pid])
                    st.rerun()
            elif lab == "Sent":
                if b.button("Open form", key=f"pv_{pid}", icon=":material/edit_document:", width="stretch", help="Participant view of the e-consent"):
                    participant_view(pid)
            elif lab == "Consent obtained":
                if b.button("Enrol", key=f"enrol_{pid}", type="primary", icon=":material/how_to_reg:", width="stretch"):
                    state.enrol(pid)
                    st.rerun()
            elif lab == "Enrolled":
                b.markdown(f'<span class="nv-muted">{c["enrolled_at"]:%d %b}</span>', unsafe_allow_html=True)
            elif lab == "Declined":
                b.markdown('<span class="nv-muted">No further contact</span>', unsafe_allow_html=True)
            with menu.popover("", icon=":material/more_vert:"):
                if lab in ("Not sent", "Sent", "Declined"):
                    if st.button("Record paper consent", key=f"paper_{pid}", icon=":material/document_scanner:", width="stretch"):
                        ss.nv_scan_pid = pid
                        st.switch_page("views/consent_scan.py")
                if lab == "Sent":
                    if st.button("Resend form", key=f"resend_{pid}", icon=":material/refresh:", width="stretch"):
                        state.send_consent([pid])
                        st.rerun()
                if lab in ("Not sent", "Sent"):
                    if st.button("Mark declined", key=f"decl_{pid}", icon=":material/block:", width="stretch"):
                        state.decline_consent(pid)
                        st.rerun()
                if lab != "Not sent":
                    if st.button("Reset consent record", key=f"reset_{pid}", icon=":material/restart_alt:", width="stretch"):
                        state.reset_consent(pid)
                        st.rerun()

st.caption("Contact details are synthetic and masked; only the data custodian role sees them in full. Study IDs are issued when consent is obtained.")
