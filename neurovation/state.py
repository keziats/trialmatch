"""Shared session state for the whole pipeline.

Patient data and criteria always come from Kezia's files in data/ (20 synthetic patients) and her
matching engine in trialmatch/. This module only adds workflow records - decisions, consent, an
activity log - which live in the browser session and are never written to data/.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from trialmatch import scoring as S

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ROLES = ["Principal investigator", "Research officer", "Data custodian"]
ROLE_NAMES = {"Principal investigator": "Dr L. Chua", "Research officer": "M. Tan", "Data custodian": "Data Office"}
CONSENT_FORM_VERSION = "v1.0"

DECISION_LABEL = {"approve": "Approved for contact", "reject": "Not eligible", "request_info": "Information requested"}


# ------------------------------------------------------------------ data (Kezia's files, read-only)
@st.cache_data
def load_patients() -> list[dict]:
    return json.loads((DATA / "patients.json").read_text(encoding="utf-8"))


@st.cache_data
def load_sample_criteria() -> list[dict]:
    return json.loads((DATA / "sample_criteria.json").read_text(encoding="utf-8"))


def patient(pid: str) -> dict:
    return next(p for p in load_patients() if p["id"] == pid)


# ------------------------------------------------------------------ session
def ss():
    s = st.session_state
    # Keys used by the protocol-matching code (originally Kezia's app.py)
    for key, default in {
        "base_criteria": None, "current": None, "method": "", "source": "",
        "version": 0, "results": None, "results_mode": "",
    }.items():
        s.setdefault(key, default)
    # Workflow keys
    s.setdefault("nv_role", ROLES[0])
    s.setdefault("nv_decisions", {})
    s.setdefault("nv_consent", {})
    s.setdefault("nv_log", [])
    s.setdefault("nv_selected", None)
    s.setdefault("nv_seq", 0)
    return s


def log(action: str, pid: str | None = None, detail: str = ""):
    s = ss()
    s.nv_log.insert(0, {"time": datetime.now(), "role": s.nv_role, "action": action, "pid": pid, "detail": detail})


def matched() -> bool:
    """True once a protocol has been submitted and patients have been ranked."""
    s = ss()
    return bool(s.results) and bool(s.current)


def ranking():
    """(criteria, results_by_pid, ranked rows) from the submitted protocol, using Kezia's scoring."""
    s = ss()
    return s.current, s.results, S.rank(load_patients(), s.results)


def protocol_name() -> str:
    s = ss()
    src = s.source or "Protocol"
    return "NCT00056563 · DBS vs best medical therapy" if "NCT00056563" in src else src.rsplit(".", 1)[0]


# ------------------------------------------------------------------ decisions
def decide(pid: str, action: str, note: str = ""):
    s = ss()
    s.nv_decisions[pid] = {"action": action, "note": note, "by": s.nv_role, "at": datetime.now()}
    log(DECISION_LABEL[action], pid, note)


def undo_decision(pid: str):
    s = ss()
    if s.nv_decisions.pop(pid, None):
        log("Decision undone", pid)


def approved() -> list[str]:
    return [pid for pid, d in ss().nv_decisions.items() if d["action"] == "approve"]


# ------------------------------------------------------------------ consent
def consent(pid: str) -> dict:
    return ss().nv_consent.get(pid, {})


def consent_label(pid: str) -> str:
    c = consent(pid)
    if c.get("enrolled_at"):
        return "Enrolled"
    return {"sent": "Sent", "obtained": "Consent obtained", "declined": "Declined"}.get(c.get("status"), "Not sent")


def send_consent(pids: list[str]):
    s = ss()
    now = datetime.now()
    for pid in pids:
        s.nv_consent[pid] = {"status": "sent", "sent_at": now, "form": CONSENT_FORM_VERSION}
        log("Consent form sent", pid, f"Electronic consent {CONSENT_FORM_VERSION}")


def _issue_study_id(pid: str):
    s = ss()
    s.nv_seq += 1
    s.nv_consent[pid]["study_id"] = f"NV-{s.nv_seq:03d}"


def record_consent(pid: str, channel: str, comprehension: int | None = None, scan_name: str | None = None, reviewer_note: str = ""):
    s = ss()
    c = s.nv_consent.setdefault(pid, {"form": CONSENT_FORM_VERSION})
    c.update({"status": "obtained", "channel": channel, "signed_at": datetime.now()})
    if comprehension is not None:
        c["comprehension"] = comprehension
    if scan_name:
        c["scan_name"] = scan_name
        c["reviewed_by"] = s.nv_role
    _issue_study_id(pid)
    how = "paper form, scan reviewed" if channel == "paper" else "electronic consent"
    log("Consent obtained", pid, f"{how}; study ID {c['study_id']}" + (f"; {reviewer_note}" if reviewer_note else ""))


def decline_consent(pid: str):
    s = ss()
    s.nv_consent.setdefault(pid, {"form": CONSENT_FORM_VERSION}).update({"status": "declined", "declined_at": datetime.now()})
    log("Consent declined", pid)


def enrol(pid: str):
    c = ss().nv_consent[pid]
    c["enrolled_at"] = datetime.now()
    log("Enrolled", pid, c.get("study_id", ""))


def reset_consent(pid: str):
    if ss().nv_consent.pop(pid, None):
        log("Consent record reset", pid)


# ------------------------------------------------------------------ synthetic contact details
def _h(pid: str, salt: str = "") -> int:
    return int(hashlib.sha256((pid + salt).encode()).hexdigest(), 16)


def contact(pid: str) -> dict:
    """Synthetic, deterministic contact details (not real, not stored in data/)."""
    n = _h(pid)
    phone = f"+65 9{n % 1000:03d} {n // 1000 % 10000:04d}"
    email = f"participant.{pid.lower().replace('-', '')}@example.sg"
    return {
        "phone": phone,
        "phone_masked": f"+65 9••• ••{phone[-2:]}",
        "email": email,
        "email_masked": f"{email[:4]}•••@example.sg",
        "mrn": f"MRN-{n % 9_000_000 + 1_000_000}",
    }


def can_reveal() -> bool:
    return ss().nv_role == "Data custodian"


# ------------------------------------------------------------------ demo helper
def simulate_replies():
    """Fill in plausible, clearly synthetic replies for patients whose consent form was sent."""
    import random

    s = ss()
    for pid, c in list(s.nv_consent.items()):
        if c.get("status") != "sent":
            continue
        rng = random.Random(pid)  # stable per patient, so the demo looks the same every time
        roll = rng.random()
        if roll < 0.55:
            record_consent(pid, "econsent", comprehension=rng.choice([4, 5, 5]))
            if rng.random() < 0.6:
                enrol(pid)
        elif roll < 0.72:
            decline_consent(pid)
        else:
            c["sent_at"] = datetime.now() - timedelta(days=rng.randint(8, 14))  # overdue
    log("Simulated participant replies", None, "Synthetic demo data")
