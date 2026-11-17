"""Tests for the workflow pages and the chatbox. The matching-engine tests live in test_core.py."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAGES = ["views/home.py", "views/protocol.py", "views/screening.py", "views/consent.py",
         "views/consent_scan.py", "views/dashboard.py", "views/chatbox.py"]


def submitted_app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.switch_page("views/protocol.py").run()
    next(b for b in at.button if b.label == "Use the bundled sample protocol").click().run()
    next(b for b in at.button if b.label == "Submit").click().run()
    assert not at.exception, at.exception
    return at


def test_every_page_renders_before_a_protocol_is_loaded():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    for page in PAGES:
        at.switch_page(page).run()
        assert not at.exception, (page, at.exception)


def test_workflow_steps_are_locked_until_submit():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert at.session_state["results"] is None
    at.switch_page("views/screening.py").run()
    assert any("Submit a protocol first" in w.value for w in at.warning)


def test_every_page_renders_after_submit():
    at = submitted_app()
    for page in PAGES:
        at.switch_page(page).run()
        assert not at.exception, (page, at.exception)


def test_screening_decisions_and_consent_flow():
    from neurovation import state

    at = submitted_app()
    at.switch_page("views/screening.py").run()
    first = at.session_state["nv_selected"]
    next(b for b in at.button if b.label == "Approve for contact").click().run()
    assert not at.exception
    assert at.session_state["nv_decisions"][first]["action"] == "approve"
    assert at.session_state["nv_selected"] != first  # moved on to the next patient

    at.switch_page("views/consent.py").run()
    next(b for b in at.button if b.label.startswith("Send to all not yet sent")).click().run()
    assert at.session_state["nv_consent"][first]["status"] == "sent"
    next(b for b in at.button if b.label == "Simulate replies (demo)").click().run()
    assert not at.exception
    assert at.session_state["nv_consent"][first]["status"] in ("obtained", "declined", "sent")
    assert state.contact(first)["phone_masked"].startswith("+65 9")


def test_research_officer_cannot_approve():
    at = submitted_app()
    at.selectbox(key="nv_role_picker").set_value("Research officer").run()
    at.switch_page("views/screening.py").run()
    assert next(b for b in at.button if b.label == "Approve for contact").disabled


def test_offline_chat_understands_patient_references():
    at = submitted_app()
    at.switch_page("views/chatbox.py").run()
    at.chat_input[0].set_value("data on patient 2 please").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "PT-102" in text and "Not eligible" in text
    at.chat_input[0].set_value("who is one criterion short?").run()
    assert "pass everything except one unknown item" in " ".join(m.value for m in at.markdown)


def test_claude_tool_loop_with_fake_client():
    """The chat loop calls tools, feeds results back, and returns the final text (no network)."""
    import streamlit as st

    from neurovation import chat
    from trialmatch import matcher as M

    patients = json.loads((ROOT / "data" / "patients.json").read_text())
    sample = json.loads((ROOT / "data" / "sample_criteria.json").read_text())
    st.session_state.update({"current": sample, "results": {p["id"]: M.match_demo(p, sample) for p in patients},
                             "source": "sample_protocol_NCT00056563.pdf", "results_mode": "Demo"})
    calls = []

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            if len(calls) == 1:
                return SimpleNamespace(stop_reason="tool_use", content=[
                    SimpleNamespace(type="tool_use", id="t1", name="get_patient", input={"patient": "patient 2"})])
            result = json.loads(kw["messages"][-1]["content"][0]["content"])
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=f"{result['id']} is {result['status']}.")])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    history = []
    answer, used = chat.ask_claude(fake, history, "Tell me about patient 2")
    assert used == ["get_patient"]
    assert answer == "PT-102 is Not eligible."
    assert calls[0]["model"] == chat.MODEL and calls[0]["tools"] == chat.TOOLS
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]


def test_matching_engine_and_data_unchanged():
    """Kezia's engine, data and scripts are used as-is."""
    diff = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", "trialmatch", "data", "scripts", "requirements.txt"],
                          cwd=ROOT, capture_output=True, text=True)
    if diff.returncode != 0:
        pytest.skip("git history not available")
    assert diff.stdout.strip() == "", diff.stdout
