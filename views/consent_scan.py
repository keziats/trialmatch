"""Paper consent: upload or photograph a signed form, review it against a checklist, approve or reject."""
import streamlit as st

from neurovation import state, ui

ss = state.ss()
if not state.matched():
    st.warning("Submit a protocol first.", icon=":material/lock:")
    st.stop()

pids = state.approved()
if st.button("Back to consent", icon=":material/arrow_back:", type="tertiary"):
    st.switch_page("views/consent.py")
ui.header(
    "Record paper consent",
    "For patients who signed a paper consent form. Upload a scan or take a photo, check the form, and approve it. "
    "Approved scans count as consent obtained.",
    [state.protocol_name(), "3 · Consent", "Paper consent"],
)
if not pids:
    st.info("No patients approved for contact yet.")
    st.stop()

default = ss.get("nv_scan_pid") if ss.get("nv_scan_pid") in pids else pids[0]
pid = st.selectbox("Patient", pids, index=pids.index(default), format_func=lambda p: f"{p} · {state.consent_label(p)}")
ss.nv_scan_pid = pid

left, right = st.columns([1.2, 1], gap="large")
with left:
    with st.container(border=True):
        st.markdown("**1 · Add the signed form**")
        src = st.segmented_control("Source", ["Upload file", "Use camera"], default="Upload file", label_visibility="collapsed")
        if src == "Use camera":
            shot = st.camera_input("Photograph the signed form", key=f"cam_{pid}")
            upload, name = shot, "camera-photo.jpg"
        else:
            upload = st.file_uploader("Scanned consent form (PDF or image)", type=["pdf", "png", "jpg", "jpeg"], key=f"scan_{pid}")
            name = upload.name if upload else None
        if upload is not None:
            if name and name.lower().endswith(".pdf"):
                st.success(f"PDF received: {name} ({upload.size / 1024:.0f} KB)", icon=":material/picture_as_pdf:")
            else:
                st.image(upload, caption=name, width="stretch")
with right:
    with st.container(border=True):
        st.markdown("**2 · Review the form**")
        checks = [
            st.checkbox(f"Correct form version ({state.CONSENT_FORM_VERSION})", key=f"chk_v_{pid}"),
            st.checkbox("Participant signature present", key=f"chk_s_{pid}"),
            st.checkbox("Signature dated", key=f"chk_d_{pid}"),
            st.checkbox("Person taking consent has signed and dated", key=f"chk_w_{pid}"),
            st.checkbox("All pages present and initialled", key=f"chk_p_{pid}"),
        ]
        note = st.text_input("Reviewer note (optional)", key=f"chk_n_{pid}")
        ready = upload is not None and all(checks)
        c1, c2 = st.columns(2)
        if c1.button("Approve scan", type="primary", icon=":material/verified:", disabled=not ready, width="stretch"):
            state.record_consent(pid, "paper", scan_name=name, reviewer_note=note)
            st.toast(f"Paper consent recorded for {pid}", icon=":material/verified:")
            st.switch_page("views/consent.py")
        if c2.button("Reject scan", icon=":material/close:", disabled=upload is None, width="stretch"):
            state.log("Paper consent scan rejected", pid, note or "Incomplete form")
            st.toast("Scan rejected. The form needs to be corrected and rescanned.", icon=":material/close:")
        if not ready:
            st.caption("Add the form and tick every check to approve.")
