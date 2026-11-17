"""Step 1 · Protocol matching.

The protocol upload, criteria extraction and criteria editor are Kezia's original tab 1 (from app.py),
moved here with the same logic. Her tab 2 (run matching) is now the Submit section at the bottom; her
tab 3 (evidence) is now the Screening page.
"""
import time

import pandas as pd
import streamlit as st

from neurovation import state, ui
from trialmatch import criteria as C
from trialmatch import matcher as M
from trialmatch.llm import get_client
from trialmatch.pdf import extract_text

SAMPLE_PDF = state.DATA / "sample_protocol_NCT00056563.pdf"
ss = state.ss()
client = get_client()
patients = state.load_patients()
sample_criteria = state.load_sample_criteria()


def set_criteria(items, method, source):
    ss.base_criteria, ss.current = items, items
    ss.method, ss.source = method, source
    ss.version += 1  # new editor state


ui.header(
    "Protocol Matching",
    "Upload the trial protocol. Its eligibility criteria are extracted into the table below; check them, then press "
    "<b>Submit</b> to rank every patient against them.",
    ["Workflow", "1 · Protocol matching"],
)

# ---------------------------------------------------------------- load a protocol (Kezia's tab 1)
with st.container(border=True):
    left, right = st.columns([2, 1], gap="large")
    with left:
        upload = st.file_uploader("Upload a protocol PDF", type=["pdf"])
        if upload is not None and st.button("Extract criteria", type="primary", icon=":material/auto_awesome:"):
            with st.spinner("Reading the protocol..."):
                try:
                    items, method = C.extract(extract_text(upload), client)
                except Exception as exc:
                    items, method = [], f"failed: {type(exc).__name__}"
            if items:
                set_criteria(items, method, upload.name)
            else:
                st.warning(
                    "No criteria found. The layout may be unusual or the PDF may be scanned. "
                    "Add criteria by hand in the table below, or set ANTHROPIC_API_KEY for AI extraction."
                )
                set_criteria([{"id": "I1", "type": "inclusion", "text": ""}], method, upload.name)
    with right:
        st.markdown("**No PDF to hand?**")
        st.caption("Load the bundled sample: eligibility criteria from the public record of NCT00056563, deep brain stimulation vs best medical therapy in Parkinson's disease.")
        if st.button("Use the bundled sample protocol", icon=":material/folder_open:"):
            items, method = C.extract(extract_text(SAMPLE_PDF), None)
            set_criteria(items, method, SAMPLE_PDF.name)

if not ss.base_criteria:
    st.info("Upload a PDF, or use the bundled sample, to begin.", icon=":material/upload_file:")
    st.stop()

# ---------------------------------------------------------------- criteria editor (Kezia's)
st.subheader("Eligibility criteria")
st.caption(f"From `{ss.source}` · extracted by {ss.method}. Edit anything that looks wrong; matching uses this table.")
edited = st.data_editor(
    pd.DataFrame(ss.base_criteria),
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    key=f"criteria_editor_{ss.version}",
    height=min(36 * (len(ss.base_criteria) + 2), 600),
    column_config={
        "id": st.column_config.TextColumn("ID", required=True, width=70),
        "type": st.column_config.SelectboxColumn("Type", options=["inclusion", "exclusion"], required=True, width=120),
        "text": st.column_config.TextColumn("Criterion", required=True, width="large"),
    },
)
current = [
    {"id": str(r["id"]).strip(), "type": r["type"], "text": str(r["text"]).strip()}
    for r in edited.to_dict("records")
    if r.get("id") and r.get("text") and str(r["text"]).strip()
]
if current != ss.current:
    ss.current, ss.results = current, None
ids = [c["id"] for c in current]
duplicate_ids = len(ids) != len(set(ids))
if duplicate_ids:
    st.error("Criterion IDs must be unique.")

# ---------------------------------------------------------------- submit (was Kezia's tab 2)
st.subheader("Submit")
demo_ok = M.demo_available(current, sample_criteria)
modes = (["Demo (precomputed verdicts)"] if demo_ok else []) + (["Live (Claude reads each note)"] if client else [])
with st.container(border=True):
    if not modes:
        st.warning(
            "Demo verdicts exist only for the bundled sample protocol, and live matching needs an "
            "ANTHROPIC_API_KEY. Use the bundled sample, or set a key.",
            icon=":material/warning:",
        )
        mode = None
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            mode = st.radio("Matching mode", modes, horizontal=True)
            st.caption(f"{len(current)} criteria × {len(patients)} synthetic patients. "
                       + ("Demo mode replays verdicts written with the synthetic patients; no AI is used." if mode.startswith("Demo")
                          else "Claude reads each note; any quote not found word for word in the note is downgraded to Unknown."))
        if state.matched() and (state.ss().nv_decisions or state.ss().nv_consent):
            c2.warning("Submitting again clears screening decisions and consent records.", icon=":material/restart_alt:")
    submit = st.button("Submit", type="primary", icon=":material/send:", disabled=not mode or duplicate_ids or not current, width="stretch")

if submit:
    bar = st.progress(0.0, text="Ranking patient data according to protocol...")
    results = {}
    for i, p in enumerate(patients, start=1):
        if mode.startswith("Demo"):
            results[p["id"]] = M.match_demo(p, current)
            time.sleep(0.04)  # keep the progress visible in demo mode
        else:
            try:
                results[p["id"]] = M.match_live(client, p, current)
            except Exception as exc:
                results[p["id"]] = [{"id": c["id"], "verdict": "unknown", "evidence": "", "flag": f"error: {type(exc).__name__}"} for c in current]
        bar.progress(i / len(patients), text=f"Ranking patient data according to protocol... {i} of {len(patients)}")
    ss.results, ss.results_mode = results, mode
    ss.nv_decisions, ss.nv_consent, ss.nv_selected, ss.nv_seq = {}, {}, None, 0
    state.log("Protocol submitted", None, f"{ss.source} · {len(current)} criteria · {mode}")
    bar.progress(1.0, text="Done. Opening the ranked patients...")
    time.sleep(0.4)
    st.switch_page("views/screening.py")

if state.matched():
    st.success("Patients are ranked against this protocol.", icon=":material/check_circle:")
    if st.button("Go to screening", icon=":material/arrow_forward:"):
        st.switch_page("views/screening.py")
