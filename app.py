"""Neurovation · clinical trial recruitment pipeline (Streamlit entry point).

Run:  streamlit run app.py

Pages live in views/. The protocol-matching engine (Kezia's trialmatch package) and its synthetic
patients in data/ are used unchanged. The original single-page app's protocol step now lives in
views/protocol.py; its ranked-patients and evidence tabs are now the Screening page.
"""
import streamlit as st

from neurovation import state, ui

st.set_page_config(page_title="Neurovation", page_icon=":material/neurology:", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)
state.ss()

PAGES = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/protocol.py", title="Protocol matching", icon=":material/description:"),
    st.Page("views/screening.py", title="Screening", icon=":material/person_search:"),
    st.Page("views/consent.py", title="Consent", icon=":material/assignment_turned_in:"),
    st.Page("views/consent_scan.py", title="Paper consent", icon=":material/document_scanner:"),
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/monitoring:"),
    st.Page("views/chatbox.py", title="Chatbox", icon=":material/chat:"),
]
page = st.navigation(PAGES, position="hidden")
ui.sidebar()
page.run()
