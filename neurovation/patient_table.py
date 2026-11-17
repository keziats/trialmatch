"""Interactive ranked-patient table (Streamlit custom component v2, no iframe).

- Hover over rank, patient, or score: pop-up with the patient's note, every evidence sentence highlighted.
- Hover over the Pass / Fail / Unknown count: pop-up listing only those criteria, with only those sentences highlighted.
- Click a row: returns the patient ID to Python (trigger value "select").

All text is escaped in Python before it reaches the component.
"""
import html

import streamlit as st

from . import ui

CSS = """
:host { display: block; }
.pt-wrap { border: 1px solid #E4E7EC; border-radius: 12px; overflow-x: auto; background: #fff;
  font-family: Inter, system-ui, -apple-system, 'Segoe UI', sans-serif; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; color: #475467; }
th { text-align: left; font-weight: 500; font-size: 12px; color: #667085; background: #F9FAFB; padding: 0 8px; height: 38px;
  border-bottom: 1px solid #E4E7EC; white-space: nowrap; }
td { padding: 9px 8px; border-bottom: 1px solid #E4E7EC; vertical-align: middle; white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
tbody tr { cursor: pointer; }
tbody tr:hover td { background: #F9FAFB; }
tbody tr.sel td { background: #EEF3FE; }
tbody tr.sel td:first-child { box-shadow: inset 3px 0 0 #2A56C6; }
.id { color: #101828; font-weight: 600; font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 13px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.score { display: flex; align-items: center; gap: 6px; min-width: 80px; }
.sub { display: block; color: #98A2B3; font-size: 11.5px; font-weight: 400; margin-top: 1px; }
.track { flex: 1; height: 6px; border-radius: 3px; background: #F2F4F7; overflow: hidden; }
.fill { height: 100%; background: #2A56C6; border-radius: 3px; }
.sv { width: 30px; text-align: right; font-weight: 600; color: #101828; font-variant-numeric: tabular-nums; }
.badge { display: inline-flex; align-items: center; gap: 6px; height: 22px; padding: 0 8px; border-radius: 6px; border: 1px solid;
  font-size: 12px; font-weight: 500; line-height: 20px; }
.badge i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: inline-block; }
.cnt { display: inline-flex; align-items: center; justify-content: center; min-width: 26px; height: 22px; padding: 0 6px; border-radius: 6px;
  font-weight: 600; font-size: 12.5px; font-variant-numeric: tabular-nums; }
.cnt.z { opacity: .35; }
.hint { color: #98A2B3; font-size: 12px; }
.pop { position: fixed; z-index: 99999; display: none; width: 420px; max-height: 70vh; overflow: auto; background: #fff;
  border: 1px solid #E4E7EC; border-radius: 12px; box-shadow: 0 12px 24px -4px rgba(16,24,40,.14), 0 4px 8px -2px rgba(16,24,40,.06);
  padding: 14px 16px; font-family: Inter, system-ui, sans-serif; font-size: 13px; color: #344054; line-height: 1.55; }
.pop h4 { margin: 0 0 2px 0; font-size: 14px; color: #101828; display: flex; align-items: center; gap: 8px; }
.pop .muted { color: #667085; font-size: 12px; }
.pop .note { margin-top: 10px; padding-top: 10px; border-top: 1px solid #E4E7EC; line-height: 1.7; }
.pop mark { padding: 1px 3px; border-radius: 4px; color: inherit; }
.pop .item { padding: 8px 0; border-bottom: 1px solid #F2F4F7; }
.pop .item:last-child { border-bottom: 0; }
.pop .q { margin-top: 4px; padding: 6px 10px; background: #F9FAFB; border: 1px solid #E4E7EC; border-radius: 8px; font-size: 12.5px; }
.pop .legend { margin-top: 8px; display: flex; gap: 12px; font-size: 11.5px; color: #667085; }
.pop .legend span::before { content: ''; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; background: var(--c); }
"""

JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  let root = parentElement.querySelector('.pt-root');
  if (!root) { root = document.createElement('div'); root.className = 'pt-root'; parentElement.appendChild(root); }
  root.innerHTML = data.table;
  let pop = parentElement.querySelector('.pop');
  if (!pop) { pop = document.createElement('div'); pop.className = 'pop'; parentElement.appendChild(pop); }
  pop.style.display = 'none';
  let timer = null;
  const place = (e) => {
    const w = pop.offsetWidth || 420, h = pop.offsetHeight || 300, pad = 14;
    let x = e.clientX + 18, y = e.clientY + 14;
    if (x + w + pad > window.innerWidth) x = Math.max(pad, e.clientX - w - 18);
    if (y + h + pad > window.innerHeight) y = Math.max(pad, window.innerHeight - h - pad);
    pop.style.left = x + 'px'; pop.style.top = y + 'px';
  };
  root.querySelectorAll('[data-pop]').forEach((cell) => {
    cell.addEventListener('mouseenter', (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const [pid, kind] = cell.dataset.pop.split('|');
        pop.innerHTML = data.pops[pid][kind];
        pop.style.display = 'block';
        place(e);
      }, 120);
    });
    cell.addEventListener('mousemove', (e) => { if (pop.style.display === 'block') place(e); });
    cell.addEventListener('mouseleave', () => { clearTimeout(timer); pop.style.display = 'none'; });
  });
  root.querySelectorAll('tr[data-pid]').forEach((tr) => {
    tr.addEventListener('click', () => { clearTimeout(timer); pop.style.display = 'none'; setTriggerValue('select', tr.dataset.pid); });
  });
}
"""

_component = st.components.v2.component("neurovation_patient_table", css=CSS, js=JS)


def _badge(text, tone):
    fg, bg, line = ui.TONES[tone]
    return f'<span class="badge" style="color:{fg};background:{bg};border-color:{line}"><i></i>{html.escape(text)}</span>'


def _cnt(n, verdict):
    fg, bg, _ = ui.TONES[ui.VERDICT_TONE[verdict]]
    return f'<span class="cnt{" z" if n == 0 else ""}" style="color:{fg};background:{bg}">{n}</span>'


LEGEND = ('<div class="legend"><span style="--c:#D1FADF">Pass</span><span style="--c:#FEE4E2">Fail</span>'
          '<span style="--c:#FEF0C7">Unknown</span></div>')


def _pops(p, row, results, criteria):
    by_id = {c["id"]: c for c in criteria}
    head = (f'<h4>{html.escape(p["id"])} {_badge(row["status"], ui.STATUS_TONE[row["status"]])}</h4>'
            f'<div class="muted">Rank {row["rank"]} · {p["age"]} y · {"female" if p["sex"] == "F" else "male"} · '
            f'match score {row["score"]:.2f} · {row["pass"]} pass, {row["fail"]} fail, {row["unknown"]} unknown</div>')
    out = {"all": head + f'<div class="note">{ui.highlight_note(p["note"], results)}</div>{LEGEND}'
                         '<div class="muted" style="margin-top:6px">Click the row to open the full record.</div>'}
    for v in ("pass", "fail", "unknown"):
        hits = [r for r in results if r["verdict"] == v]
        if not hits:
            out[v] = head + f'<div class="note">No criterion is {ui.VERDICT_LABEL[v].lower()} for this patient.</div>'
            continue
        items = "".join(
            f'<div class="item"><b>{html.escape(r["id"])}</b> {html.escape(by_id.get(r["id"], {}).get("text", ""))}'
            + (f'<div class="q">“{html.escape(r["evidence"])}”</div>' if r.get("evidence") else '<div class="muted">Not stated in the note.</div>')
            + "</div>"
            for r in hits
        )
        title = f'{ui.VERDICT_LABEL[v]} · {len(hits)} criteri{"on" if len(hits) == 1 else "a"}'
        out[v] = (f'<h4>{html.escape(p["id"])} · {title}</h4>{items}'
                  f'<div class="note">{ui.highlight_note(p["note"], results, only=v)}</div>')
    return out


def patient_table(rows, results_by_pid, criteria, patients_by_id, decisions, selected, key="ptable"):
    """Render the table; return the patient ID the user clicked (or None)."""
    body, pops = [], {}
    for r in rows:
        pid = r["id"]
        p = patients_by_id[pid]
        pops[pid] = _pops(p, r, results_by_pid[pid], criteria)
        d = decisions.get(pid)
        short = {"approve": "Approved", "reject": "Not eligible", "request_info": "Info needed"}
        dec = _badge(short[d["action"]], ui.DECISION_TONE[d["action"]]) if d else '<span class="hint">To review</span>'
        body.append(
            f'<tr data-pid="{html.escape(pid)}" class="{"sel" if pid == selected else ""}">'
            f'<td class="num" data-pop="{pid}|all">{r["rank"]}</td>'
            f'<td data-pop="{pid}|all"><span class="id">{html.escape(pid)}</span><span class="sub">{p["age"]} y · {p["sex"]}</span></td>'
            f'<td data-pop="{pid}|all"><div class="score"><div class="track"><div class="fill" style="width:{r["score"] * 100:.0f}%"></div></div>'
            f'<span class="sv">{r["score"]:.2f}</span></div></td>'
            f'<td>{_badge(r["status"], ui.STATUS_TONE[r["status"]])}</td>'
            f'<td data-pop="{pid}|pass">{_cnt(r["pass"], "pass")}</td>'
            f'<td data-pop="{pid}|fail">{_cnt(r["fail"], "fail")}</td>'
            f'<td data-pop="{pid}|unknown">{_cnt(r["unknown"], "unknown")}</td>'
            f"<td>{dec}</td></tr>"
        )
    table = ('<div class="pt-wrap"><table><thead><tr><th class="num">Rank</th><th>Patient</th><th>Match score</th>'
             '<th>Status</th><th title="Pass">Pass</th><th title="Fail">Fail</th><th title="Unknown">Unk.</th><th>Decision</th></tr></thead><tbody>'
             + "".join(body) + "</tbody></table></div>")
    result = _component(data={"table": table, "pops": pops}, key=key, on_select_change=lambda: None)
    return getattr(result, "select", None)
