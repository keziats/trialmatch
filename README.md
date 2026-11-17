# Neurovation: clinical trial recruitment

Neurovation reads a trial protocol, checks every patient's notes against each eligibility criterion, and ranks who is likely eligible, with the exact sentence behind every verdict. The clinician then approves who to contact, sends consent forms (or records paper consent), and tracks recruitment, all in one app.

All patients are **synthetic**. The match score only orders the review queue; **a clinician makes every decision**.

## Quick start

You need Python 3.10 or newer.

    pip install -r requirements.txt
    streamlit run app.py

1. **Home** → **Get started**.
2. **Protocol matching**: **Use the bundled sample protocol** (or upload a PDF), check the criteria, then **Submit**. A progress bar ranks the patients, and the Screening page opens.
3. **Screening**: hover over a patient to preview the evidence; click to open the record; **Approve for contact**, **Need more info** or **Not eligible**. The next patient opens automatically.
4. **Consent**: **Send to all not yet sent** (or tick patients and **Send to selected**). For the demo, **Simulate replies** fills in synthetic answers. Use the ⋮ menu → **Record paper consent** to review a scanned form.
5. **Dashboard** and **Chatbox**: see where recruitment stalls, and ask questions in plain language.

Run the tests with `python -m pytest`.

## Pages

| Sidebar | What it does |
|---|---|
| **Home** | What the software does, the four steps, **Get started**. |
| **1 · Protocol matching** | Upload a protocol PDF (or the bundled sample). Criteria are extracted by Claude, or by a rule-based parser without an API key, into an editable table. **Submit** matches every patient (Demo or Live mode) with a progress bar. |
| **2 · Screening** | Locked until a protocol is submitted. Ranked table with colour-coded status. **Hover** over rank, patient or score for the highlighted clinic note; **hover** over the Pass / Fail / Unknown count for just those criteria, with just those sentences highlighted. **Click** a row to open the record beside the table: criteria with quoted evidence, the highlighted clinic note, the activity history, and the decision buttons. This page replaces the original "Ranked patients" and "Evidence" tabs and the separate review page, which showed the same information three times. |
| **3 · Consent** | Approved patients, with rank, screening status, masked contact details, consent status (Not sent / Sent / Consent obtained / Declined / Enrolled) and one action per row: send, open the participant's e-consent form (5-question comprehension check, below 4/5 triggers a call-back), enrol. Bulk send to selected or to all. The ⋮ menu: record paper consent, resend, mark declined, reset. |
| Paper consent | Opened from the Consent page. Upload a scan or take a photo of the signed form, tick the review checklist, then **Approve scan**: the patient shows **Consent obtained (paper)**. |
| **Dashboard** | Headline numbers (each opens the right page), a clickable funnel, "needs attention" lists, why patients are excluded and what the notes don't say (click a bar to list those patients), and recent activity. Every patient ID opens that patient's record. |
| **Chatbox** | Questions in plain language: "Tell me about patient 2", "Who is one criterion short?", "Where are we with consent?". With `ANTHROPIC_API_KEY` set, Claude answers using tools that look everything up in the study data (model `claude-opus-5-5`, override with `CHATBOX_MODEL`). Without a key, built-in offline answers cover the common questions. |

### Roles (sidebar → Signed in as)

| Role | Can do |
|---|---|
| Principal investigator (default) | Everything, including **approve for contact** |
| Research officer | Review, request information, mark not eligible, run consent; cannot approve |
| Data custodian | Sees full (synthetic) contact details on the Consent page |

## Protocol matching engine (`trialmatch/`)

### Modes

| Mode | Needs | What it does |
|---|---|---|
| Demo | nothing | Precomputed verdicts for the bundled sample protocol. No AI. |
| Live | `ANTHROPIC_API_KEY` | Claude reads each note, gives pass/fail/unknown with a quoted sentence. Evidence not found word for word in the note is downgraded to unknown. |

Set a key in PowerShell with `$env:ANTHROPIC_API_KEY="sk-..."` (macOS/Linux: `export ANTHROPIC_API_KEY=sk-...`). On Streamlit Community Cloud, add it under the app's **Settings → Secrets** as `ANTHROPIC_API_KEY = "sk-..."`. Matching model: `$env:TRIALMATCH_MODEL` (default `claude-sonnet-5-5`).

Without a key, uploaded PDFs use rule-based criteria extraction (bulleted or "(a) ... (b) ..." layouts). Check the criteria table and fix it by hand before submitting.

### Score

Score = (passes + 0.5 × unknowns) ÷ criteria, halved for each fail. Status: any fail → **Not eligible**; no fail and no unknown → **Likely eligible**; otherwise **Needs review**. A heuristic for ordering the queue, not a validated model.

### Honest status

- Tested: PDF extraction, scoring, evidence validation, demo flow, every page (`pytest`), and the chatbox's Claude tool loop against a fake client.
- **Not yet tested with a real API key: live matching and the Claude chatbox.** Try them on your machine first.
- The bundled PDF is a **test fixture** written from the public ClinicalTrials.gov record NCT00056563 (deep brain stimulation vs best medical therapy in Parkinson's disease), not the original protocol.

### Real protocol to try

Zoon et al. 2024, *Trials* (CC BY 4.0): https://trialsjournal.biomedcentral.com/articles/10.1186/s13063-024-07938-9 → Download PDF. There are no correct answers for it, so read the evidence yourself.

## Data

- `data/patients.json`: **20 synthetic patients** (PT-101 to PT-120), each with age, sex, one free-text clinic note, and the correct verdict with evidence for the 11 sample criteria. Generated by `scripts/make_patients.py`.
- `data/sample_criteria.json`: the 11 criteria (6 inclusion, 5 exclusion) from the fixture protocol.
- The app adds **workflow records only**: decisions, consent, study IDs and an activity log, held in the browser session and never written to `data/`. Contact details are synthetic, generated from the study ID, and masked unless the role is data custodian.

## Layout

    app.py                     entry point: page list, shared look, sidebar
    views/                     one file per page
      home.py  protocol.py  screening.py  consent.py  consent_scan.py  dashboard.py  chatbox.py
    neurovation/               shared app code
      state.py                 session state: protocol, results, decisions, consent, activity log
      ui.py                    design tokens, badges, page header, sidebar navigation
      patient_table.py         interactive ranked table (hover previews, click to open)
      chat.py                  chatbox: Claude with data-lookup tools, plus offline answers
    trialmatch/                protocol-matching engine: pdf, criteria, matcher, scoring, llm
    scripts/                   make_fixture.py, make_patients.py (regenerate data/)
    data/                      fixture PDF, 20 synthetic patients, sample criteria
    tests/                     test_core.py (engine), test_neurovation.py (pages, workflow, chatbox)
    .streamlit/config.toml     theme

## Limits

- Workflow records last for the browser session; there is no database yet.
- Correct answers exist only for the bundled sample protocol.
- All patients and contact details are synthetic. Not for clinical use.
