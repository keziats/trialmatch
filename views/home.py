"""Landing page."""
import streamlit as st

from neurovation import state, ui

st.markdown(
    f"""
<div style="max-width:880px;margin:4vh auto 0 auto;text-align:left">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px">{ui.LOGO.replace('width="28" height="28"', 'width="44" height="44"')}
    <span style="font-size:15px;font-weight:600;color:{ui.MUTED};letter-spacing:.04em;text-transform:uppercase">Neurovation</span></div>
  <h1 style="font-size:2.6rem;line-height:1.15;margin:0 0 14px 0;color:{ui.INK}">Find the right patients for a clinical trial in minutes, not weeks.</h1>
  <p style="font-size:17px;color:#475467;line-height:1.6;margin:0 0 8px 0">
    Neurovation reads a trial protocol, checks every patient's notes against each eligibility criterion,
    and ranks who is likely eligible, showing the exact sentence behind every decision.
    The clinician then approves who to contact, sends consent forms, and tracks recruitment in one place.</p>
  <p style="font-size:13px;color:{ui.MUTED};margin:0">For clinical research teams · decision support only · a clinician makes every decision · demo uses synthetic patients</p>
</div>
""",
    unsafe_allow_html=True,
)
st.write("")
_, mid, _ = st.columns([1, 2.2, 1])
with mid:
    if st.button("Get started", type="primary", icon=":material/arrow_forward:", width="stretch"):
        st.switch_page("views/protocol.py")
    st.write("")
    steps = [
        ("description", "1 · Protocol matching", "Upload the protocol. Eligibility criteria are extracted and patients are ranked against them."),
        ("person_search", "2 · Screening", "Review each patient's evidence, criterion by criterion, and approve who may be contacted."),
        ("assignment_turned_in", "3 · Consent", "Send electronic consent forms, or record paper consent, and enrol participants."),
        ("monitoring", "Dashboard and chatbox", "See where recruitment stalls and ask questions about the study in plain language."),
    ]
    cols = st.columns(2)
    for i, (icon, title, text) in enumerate(steps):
        with cols[i % 2].container(border=True, height=150):
            st.markdown(f":material/{icon}: **{title}**")
            st.caption(text)
    if state.matched():
        st.info(f"A protocol is already loaded ({state.protocol_name()}). Continue on the Screening page.", icon=":material/info:")
