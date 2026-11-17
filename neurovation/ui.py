"""Shared look and navigation: global CSS, badges, page header, sidebar."""
import html

import streamlit as st

from trialmatch.llm import get_client

from . import state

# ------------------------------------------------------------------ design tokens (match the Neurovation design system)
INK, TEXT, MUTED, FAINT, BORDER = "#101828", "#344054", "#667085", "#98A2B3", "#E4E7EC"
PRIMARY = "#2A56C6"
TONES = {
    "ok": ("#067647", "#ECFDF3", "#ABEFC6"),
    "bad": ("#B42318", "#FEF3F2", "#FECDCA"),
    "warn": ("#B54708", "#FFFAEB", "#FEDF89"),
    "blue": ("#2A56C6", "#EEF3FE", "#C7D6FB"),
    "grey": ("#344054", "#F9FAFB", "#E4E7EC"),
}
VERDICT_TONE = {"pass": "ok", "fail": "bad", "unknown": "warn"}
VERDICT_LABEL = {"pass": "Pass", "fail": "Fail", "unknown": "Unknown"}
STATUS_TONE = {"Likely eligible": "ok", "Needs review": "warn", "Not eligible": "bad"}
DECISION_TONE = {"approve": "blue", "reject": "bad", "request_info": "warn"}
CONSENT_TONE = {"Not sent": "grey", "Sent": "warn", "Consent obtained": "ok", "Declined": "bad", "Enrolled": "blue"}

CSS = f"""
<style>
.block-container {{padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1400px;}}
[data-testid="stSidebar"] {{border-right: 1px solid {BORDER};}}
[data-testid="stSidebarNavItems"], [data-testid="stSidebarNav"] {{display: none;}}
h1 {{letter-spacing: -0.015em;}}
.nv-crumbs {{font-size: 13px; color: {MUTED}; margin-bottom: 2px;}}
.nv-crumbs b {{color: {TEXT}; font-weight: 500;}}
.nv-sub {{color: #475467; font-size: 14.5px; max-width: 860px; margin: -4px 0 6px 0;}}
.nv-badge {{display: inline-flex; align-items: center; gap: 6px; height: 22px; padding: 0 8px; border-radius: 6px;
  border: 1px solid; font-size: 12px; font-weight: 500; white-space: nowrap; line-height: 20px;}}
.nv-badge i {{width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: inline-block;}}
.nv-quote {{margin-top: 6px; padding: 8px 12px; background: #F9FAFB; border: 1px solid {BORDER}; border-radius: 8px;
  font-size: 13px; color: {TEXT};}}
.nv-muted {{color: {MUTED}; font-size: 12.5px;}}
.nv-crit {{display: grid; grid-template-columns: 22px 1fr; gap: 10px; padding: 12px 0; border-bottom: 1px solid {BORDER};}}
.nv-crit:last-child {{border-bottom: 0;}}
.nv-vicon {{width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; font-size: 11px; font-weight: 700; margin-top: 1px;}}
.nv-note {{line-height: 1.75; font-size: 14px; color: {TEXT};}}
.nv-note mark {{padding: 1px 3px; border-radius: 4px; color: inherit;}}
.nv-kv {{display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; margin: 6px 0 4px;}}
.nv-kv div {{font-size: 12px; color: {MUTED};}}
.nv-kv b {{display: block; font-size: 14px; color: {INK}; font-weight: 600; margin-top: 2px;}}
.nv-brand {{display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 16px; color: {INK}; margin: 0 0 4px 2px;}}
.nv-row {{display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid {BORDER}; font-size: 14px;}}
.nv-row:last-child {{border-bottom: 0;}}
div[data-testid="stMetricValue"] {{font-size: 26px;}}
</style>
"""

LOGO = """<svg width="28" height="28" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0f2742"/>
<path d="M7 19c3 0 3-7 6-7s3 10 6 10 3-6 6-6" fill="none" stroke="#8fb0f2" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

MARK_BG = {"pass": "#D1FADF", "fail": "#FEE4E2", "unknown": "#FEF0C7"}


def badge(text: str, tone: str = "grey") -> str:
    fg, bg, line = TONES[tone]
    return f'<span class="nv-badge" style="color:{fg};background:{bg};border-color:{line}"><i></i>{html.escape(text)}</span>'


def verdict_icon(v: str) -> str:
    fg, bg, _ = TONES[VERDICT_TONE[v]]
    sym = {"pass": "✓", "fail": "✕", "unknown": "?"}[v]
    return f'<span class="nv-vicon" style="color:{fg};background:{bg}">{sym}</span>'


def highlight_note(note: str, results: list[dict], only: str | None = None) -> str:
    """Return the note as HTML with evidence sentences highlighted by verdict (optionally one verdict only)."""
    body = html.escape(note)
    for r in results:
        if not r.get("evidence") or (only and r["verdict"] != only):
            continue
        e = html.escape(r["evidence"])
        body = body.replace(e, f'<mark style="background:{MARK_BG[r["verdict"]]}" title="{html.escape(r["id"])}">{e}</mark>', 1)
    return body


def header(title: str, sub: str = "", crumbs: list[str] | None = None):
    if crumbs:
        st.markdown('<div class="nv-crumbs">' + " / ".join(html.escape(c) for c in crumbs[:-1])
                    + (" / " if len(crumbs) > 1 else "") + f"<b>{html.escape(crumbs[-1])}</b></div>", unsafe_allow_html=True)
    st.title(title)
    if sub:
        st.markdown(f'<div class="nv-sub">{sub}</div>', unsafe_allow_html=True)


def open_patient(pid: str, page: str = "views/screening.py"):
    state.ss().nv_selected = pid
    st.switch_page(page)


# ------------------------------------------------------------------ sidebar
def sidebar():
    s = state.ss()
    ready = state.matched()
    with st.sidebar:
        st.markdown(f'<div class="nv-brand">{LOGO}<span>Neurovation</span></div>', unsafe_allow_html=True)
        st.caption("Clinical trial recruitment")
        st.page_link("views/home.py", label="Home", icon=":material/home:")
        st.caption("**Workflow**")
        st.page_link("views/protocol.py", label="1 · Protocol matching", icon=":material/description:")
        n_queue = sum(1 for r in state.ranking()[2] if r["status"] != "Not eligible" and r["id"] not in s.nv_decisions) if ready else 0
        st.page_link("views/screening.py", label=f"2 · Screening{f'  ({n_queue} to review)' if n_queue else ''}",
                     icon=":material/person_search:", disabled=not ready, help=None if ready else "Submit a protocol first")
        n_appr = len(state.approved())
        st.page_link("views/consent.py", label=f"3 · Consent{f'  ({n_appr} approved)' if n_appr else ''}",
                     icon=":material/assignment_turned_in:", disabled=not ready, help=None if ready else "Submit a protocol first")
        st.caption("**Overview**")
        st.page_link("views/dashboard.py", label="Dashboard", icon=":material/monitoring:", disabled=not ready,
                     help=None if ready else "Submit a protocol first")
        st.page_link("views/chatbox.py", label="Chatbox", icon=":material/chat:", disabled=not ready,
                     help=None if ready else "Submit a protocol first")

        st.divider()
        st.markdown("**Status**")
        if get_client():
            st.success("Claude connected", icon=":material/check_circle:")
        else:
            st.info("Offline mode: no ANTHROPIC_API_KEY. Demo matching, rule-based extraction and offline chat answers.", icon=":material/info:")
        st.caption(f"{len(state.load_patients())} synthetic patients loaded"
                   + (f" · protocol: {state.protocol_name()}" if ready else " · no protocol yet"))

        st.divider()
        st.markdown("**Signed in as**")
        role = st.selectbox("Role", state.ROLES, index=state.ROLES.index(s.nv_role), label_visibility="collapsed", key="nv_role_picker",
                            format_func=lambda r: f"{state.ROLE_NAMES[r]} · {r}")
        if role != s.nv_role:
            s.nv_role = role
            state.log("Switched role", None, role)
        st.caption("Only the principal investigator can approve patients for contact. Only the data custodian can see full contact details.")
