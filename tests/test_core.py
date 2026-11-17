import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trialmatch import criteria as C  # noqa: E402
from trialmatch import matcher as M  # noqa: E402
from trialmatch import scoring as S  # noqa: E402
from trialmatch.llm import parse_json  # noqa: E402
from trialmatch.pdf import extract_text  # noqa: E402

PATIENTS = json.loads((ROOT / "data" / "patients.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((ROOT / "data" / "sample_criteria.json").read_text(encoding="utf-8"))


def test_sample_pdf_extracts_eleven_criteria():
    items = C.extract_heuristic(extract_text(ROOT / "data" / "sample_protocol_NCT00056563.pdf"))
    assert [c["id"] for c in items] == ["I1", "I2", "I3", "I4", "I5", "I6", "E1", "E2", "E3", "E4", "E5"]
    assert items == SAMPLE


def test_inline_style_protocol_paper():
    text = ("The inclusion criteria are as follows: (a) idiopathic PD, (b) at least 3 months of STN DBS, and "
            "(c) a score of 14 or more. Exclusion criteria are as follows: (a) complications, (b) cognitive decline. Next.")
    items = C.extract_heuristic(text)
    assert [c["type"] for c in items] == ["inclusion"] * 3 + ["exclusion"] * 2
    assert items[1]["text"] == "at least 3 months of STN DBS"


def test_score_rules():
    r = lambda *v: [{"id": str(i), "verdict": x, "evidence": ""} for i, x in enumerate(v)]
    assert S.score_patient(r("pass", "pass"))["status"] == "Likely eligible"
    assert S.score_patient(r("pass", "pass"))["score"] == 1.0
    assert S.score_patient(r("pass", "unknown"))["status"] == "Needs review"
    assert S.score_patient(r("pass", "unknown"))["score"] == 0.75
    s = S.score_patient(r("pass", "fail"))
    assert s["status"] == "Not eligible" and s["score"] == 0.25


def test_every_bundled_patient_has_one_truth_row_per_criterion_and_evidence_in_note():
    for p in PATIENTS:
        assert [t["id"] for t in p["truth"]] == [c["id"] for c in SAMPLE]
        for t in p["truth"]:
            if t["verdict"] != "unknown" or t["evidence"]:
                assert t["evidence"] in p["note"], (p["id"], t)
            if t["verdict"] in ("pass", "fail"):
                assert t["evidence"], (p["id"], t)


def test_demo_ranking_orders_by_score_and_covers_all_statuses():
    results = {p["id"]: M.match_demo(p, SAMPLE) for p in PATIENTS}
    ranked = S.rank(PATIENTS, results)
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert {r["status"] for r in ranked} == {"Likely eligible", "Needs review", "Not eligible"}
    assert ranked[0]["rank"] == 1


def test_validate_downgrades_fabricated_evidence():
    patient = {"note": "The patient is 60 years old. MRI normal."}
    crit = [{"id": "I1", "type": "inclusion", "text": "x"}, {"id": "I2", "type": "inclusion", "text": "y"}]
    raw = [{"id": "I1", "verdict": "pass", "evidence": "MRI normal."},
           {"id": "I2", "verdict": "pass", "evidence": "Made-up sentence."}]
    out = M.validate(raw, patient, crit)
    assert out[0]["verdict"] == "pass"
    assert out[1]["verdict"] == "unknown" and out[1]["flag"] == "evidence_not_in_note"


def test_validate_fills_missing_criteria_and_bad_verdicts():
    out = M.validate([{"id": "I1", "verdict": "maybe", "evidence": ""}], {"note": "n"},
                     [{"id": "I1", "type": "inclusion", "text": "x"}, {"id": "I2", "type": "inclusion", "text": "y"}])
    assert [o["verdict"] for o in out] == ["unknown", "unknown"]


def test_demo_only_for_unedited_sample_criteria():
    assert M.demo_available(SAMPLE, SAMPLE)
    edited = [dict(c) for c in SAMPLE]
    edited[0]["text"] = "something else"
    assert not M.demo_available(edited, SAMPLE)


def test_parse_json_handles_fences_and_prose():
    assert parse_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parse_json('Here you go: [{"a": 1}] Hope that helps') == [{"a": 1}]


def test_compare_perfect_and_degraded():
    truth = {p["id"]: p["truth"] for p in PATIENTS}
    assert S.compare(truth, truth)["criterion_agreement"] == 1.0
    wrong = {pid: [dict(r, verdict="unknown") for r in rs] for pid, rs in truth.items()}
    cmp = S.compare(truth, wrong)
    assert cmp["criterion_agreement"] < 1.0 and cmp["recall_of_possible_eligibles"] == 1.0


def test_app_smoke():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    at.switch_page("views/protocol.py").run()  # the protocol step now has its own page
    next(b for b in at.button if b.label == "Use the bundled sample protocol").click().run()
    assert not at.exception
    next(b for b in at.button if b.label == "Submit").click().run()  # was "Run matching"
    assert not at.exception
    assert len(at.session_state["results"]) == len(PATIENTS)
