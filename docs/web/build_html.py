"""Build tableau_notes.html: a single-file, single-page app with the FY26 permit dashboards and the prep notes.

The data views (Dashboard, Where Times Differ, Data Segmentation, Worksheets) mirror the dashboards and worksheets
in FY26_Public_Space_Permit_Approvals.twbx. This script embeds the in-scope permits as compact JSON; app.js
(which must sit next to the page) generates those views' tabs, layouts, filters and charts in the browser.

Usage: python3 build_html.py
"""
import csv
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent.parent / "data"
SOURCES = [
    ("guide", "Prep Guide", HERE / "tableau_walk_through.md"),
    ("qa", "Q&A Practice", HERE / "tableau_QA.md"),
]
OUT = HERE / "tableau_notes.html"
FY_START, FY_END = "2025-10-01", "2026-09-30"
DICT_COLS = {"cat": "PermitCategory", "fam": "WorkTypeFamily", "app": "ApplicantType",
             "loc": "LocationBucket", "ward": "Ward"}


def inline(text):
    codes = []

    def stash(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render_list(lines):
    """Render consecutive list lines (with 2-space nesting) into nested ul/ol."""
    out, stack = [], []  # stack of (indent, tag)
    for line in lines:
        indent = len(line) - len(line.lstrip())
        item = line.strip()
        ordered = bool(re.match(r"\d+\.\s", item))
        tag = "ol" if ordered else "ul"
        content = re.sub(r"^(\d+\.|[-*])\s+", "", item)
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if not stack or indent > stack[-1][0]:
            out.append(f"<{tag}>")
            stack.append((indent, tag))
        else:
            out.append("</li>")
        out.append(f"<li>{inline(content)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def render_table(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    head, body = rows[0], rows[2:]
    h = "".join(f"<th>{inline(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def convert(md, tab_id):
    """Return (html, toc, title). `### Q:` headings become collapsible cards."""
    lines = md.splitlines()
    out, toc, title = [], [], ""
    in_qa = False
    para = []
    i = 0

    def flush_para():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def close_qa():
        nonlocal in_qa
        if in_qa:
            out.append("</div></details>")
            in_qa = False

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if not s:
            flush_para()
        elif m:
            flush_para()
            level, text = len(m.group(1)), m.group(2)
            close_qa()
            if level == 1:
                title = text
            elif level == 2:
                sid = f"{tab_id}-{slug(text)}"
                toc.append((sid, text))
                out.append(f'<h2 id="{sid}">{inline(text)}</h2>')
            elif text.startswith("Q:"):
                in_qa = True
                out.append(
                    f'<details class="qa"><summary><span class="q-tag">Q</span>'
                    f"<span>{inline(text[2:].strip())}</span></summary><div class=\"ans\">"
                )
            else:
                out.append(f'<h3 id="{tab_id}-{slug(text)}">{inline(text)}</h3>')
        elif s == "---":
            flush_para()
            close_qa()
        elif s.startswith(">"):
            flush_para()
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip()[1:].strip())
                i += 1
            paras = " ".join(b if b else "\n" for b in block).split("\n")
            out.append("<blockquote>" + "".join(f"<p>{inline(p.strip())}</p>" for p in paras if p.strip()) + "</blockquote>")
            continue
        elif s.startswith("|"):
            flush_para()
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(render_table(block))
            continue
        elif re.match(r"([-*]|\d+\.)\s", s):
            flush_para()
            block = []
            while i < len(lines) and re.match(r"\s*([-*]|\d+\.)\s", lines[i]):
                block.append(lines[i])
                i += 1
            out.append(render_list(block))
            continue
        else:
            para.append(s)
        i += 1
    flush_para()
    close_qa()
    return "\n".join(out), toc, title


def load_permits():
    """Return the FY26 scope (new permits applied for on/after 10/1/2025 and issued in FY26) as column arrays.

    Text columns are dictionary-coded to keep the embedded JSON small (~3,000 permits).
    """
    with open(DATA / "permits_by_tracking_number.csv", newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r["NewOrRenewal"] == "New" and r["IssuedInFY26"] == "1" and r["ApplicationDate"] >= FY_START]
    dicts = {k: [] for k in DICT_COLS}
    index = {k: {} for k in DICT_COLS}
    cols = {k: [] for k in [*DICT_COLS, "month", "resub", "psc", "blocks", "a", "i"]}

    def num(v):
        return int(float(v)) if v else None

    for r in rows:
        for k, field in DICT_COLS.items():
            v = r[field] or "Unknown"
            if v not in index[k]:
                index[k][v] = len(dicts[k])
                dicts[k].append(v)
            cols[k].append(index[k][v])
        cols["month"].append(r["ApplicationDate"][:7])
        cols["resub"].append(int(r["ResubmissionRequested"] == "Yes"))
        cols["psc"].append(int(r["PSCReview"] == "Yes"))
        cols["blocks"].append(int(r["NumBlockLocations"]))
        cols["a"].append(num(r["BusinessDaysToApprove_QA"]))
        cols["i"].append(num(r["BusinessDaysToIssue_QA"]))
    with open(DATA / "dc_holidays.csv", newline="", encoding="utf-8") as f:
        holidays = [h for h in csv.DictReader(f) if FY_START <= h["HolidayDate"] <= FY_END]
    return {"dict": dicts, "cols": cols, "holidays": holidays}


def build():
    tabs, panels = [], []
    for tab_id, label, path in SOURCES:
        body, toc, title = convert(path.read_text(encoding="utf-8"), tab_id)
        toc_html = "".join(f'<li><a href="#{sid}">{inline(t)}</a></li>' for sid, t in toc)
        tools = ""
        if tab_id == "qa":
            count = body.count('class="qa"')
            tools = (
                '<div class="qa-tools">'
                '<input type="search" id="qa-search" placeholder="Filter questions…" aria-label="Filter questions">'
                '<button type="button" data-act="expand">Expand all</button>'
                '<button type="button" data-act="collapse">Collapse all</button>'
                '<button type="button" data-act="random">Random question</button>'
                f'<span class="qa-count" id="qa-count">{count} questions</span>'
                "</div>"
            )
        tabs.append(
            f'<button role="tab" id="tab-{tab_id}" aria-controls="panel-{tab_id}" '
            f'data-tab="{tab_id}" aria-selected="false">{html.escape(label)}</button>'
        )
        panels.append(
            f'<section role="tabpanel" id="panel-{tab_id}" aria-labelledby="tab-{tab_id}" hidden>'
            f'<div class="layout"><nav class="toc" aria-label="Sections"><p class="toc-title">Sections</p><ol>{toc_html}</ol></nav>'
            f'<article><h1>{inline(title)}</h1>{tools}{body}</article></div></section>'
        )
    data = json.dumps(load_permits(), separators=(",", ":")).replace("</", "<\\/")
    page = (PAGE.replace("{{TABS}}", "".join(tabs)).replace("{{PANELS}}", "\n".join(panels))
            .replace("{{DATA}}", data))
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT}")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FY26 Permit Approvals</title>
<style>
:root {
  --bg: #f7f6f3; --surface: #ffffff; --text: #1d1d1f; --muted: #5f6368;
  --border: #e2e0db; --accent: #1f5fae; --accent-soft: #e7eef8;
  --code-bg: #f0eee9; --quote: #f3f1ec; --shadow: 0 1px 2px rgba(0,0,0,.05);
  --s1: #2a78d6; --s2: #eb6834; --grid: #e7e5e0; --ref: #52514e;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #141517; --surface: #1c1d20; --text: #e6e6e6; --muted: #a0a4ab;
    --border: #2f3136; --accent: #7fb0ec; --accent-soft: #1f2a3a;
    --code-bg: #26282c; --quote: #202226; --shadow: none;
    --s1: #3987e5; --s2: #d95926; --grid: #2c2e32; --ref: #c3c2b7;
  }
}
:root[data-theme="dark"] {
  --bg: #141517; --surface: #1c1d20; --text: #e6e6e6; --muted: #a0a4ab;
  --border: #2f3136; --accent: #7fb0ec; --accent-soft: #1f2a3a;
  --code-bg: #26282c; --quote: #202226; --shadow: none;
  --s1: #3987e5; --s2: #d95926; --grid: #2c2e32; --ref: #c3c2b7;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 120px; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
header {
  position: sticky; top: 0; z-index: 10; background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.bar { max-width: 1280px; margin: 0 auto; padding: 0 16px; display: flex; align-items: center; gap: 16px; }
.brand { font-weight: 650; font-size: 15px; white-space: nowrap; }
[role="tablist"] { display: flex; gap: 4px; overflow-x: auto; }
[role="tab"] {
  appearance: none; border: 0; background: none; color: var(--muted);
  font: inherit; font-weight: 550; padding: 16px 12px 14px; cursor: pointer;
  border-bottom: 2px solid transparent; white-space: nowrap; border-radius: 0;
}
[role="tab"]:hover { border-color: transparent; color: var(--text); }
[role="tab"][aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); }
[role="tab"]:focus-visible, button:focus-visible, a:focus-visible, summary:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.theme-btn { margin-left: auto; }
button, input[type="search"], select {
  font: inherit; font-size: 14px; color: var(--text); background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 12px;
}
button { cursor: pointer; }
button:hover { border-color: var(--accent); }
.filters { border-top: 1px solid var(--border); }
.filters .bar { flex-wrap: wrap; gap: 8px 12px; padding-top: 8px; padding-bottom: 8px; }
.filters label { display: flex; flex-direction: column; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.filters select { padding: 4px 8px; font-size: 13.5px; text-transform: none; letter-spacing: 0; max-width: 220px; }
.filters .match { margin-left: auto; font-size: 13px; color: var(--muted); }
.filters .match b { color: var(--text); }
.layout { max-width: 1180px; margin: 0 auto; padding: 24px 16px 64px; display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 32px; }
.toc { position: sticky; top: 76px; align-self: start; max-height: calc(100vh - 96px); overflow-y: auto; font-size: 14px; }
.toc-title { margin: 0 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.toc ol { list-style: none; margin: 0; padding: 0; }
.toc a { display: block; padding: 5px 10px; border-radius: 6px; color: var(--muted); text-decoration: none; border-left: 2px solid transparent; }
.toc a:hover { color: var(--text); background: var(--accent-soft); }
.toc a.active { color: var(--accent); border-left-color: var(--accent); background: var(--accent-soft); }
article {
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 32px 40px; box-shadow: var(--shadow); min-width: 0;
}
h1 { font-size: 28px; line-height: 1.25; margin: 0 0 16px; }
h2 { font-size: 21px; margin: 40px 0 12px; padding-top: 16px; border-top: 1px solid var(--border); }
h3 { font-size: 17px; margin: 28px 0 8px; }
p { margin: 0 0 12px; }
ul, ol { margin: 0 0 12px; padding-left: 24px; }
li { margin: 3px 0; }
li > ul, li > ol { margin: 4px 0; }
code { font: 13.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }
strong { font-weight: 650; }
blockquote { margin: 0 0 16px; padding: 14px 18px; background: var(--quote); border-left: 3px solid var(--accent); border-radius: 0 8px 8px 0; }
blockquote p:last-child { margin-bottom: 0; }
.table-wrap { overflow-x: auto; margin: 0 0 16px; border: 1px solid var(--border); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 14.5px; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: var(--code-bg); font-weight: 600; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.qa-tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 0 0 8px; }
.qa-tools input { flex: 1 1 220px; min-width: 0; }
.qa-count { font-size: 13px; color: var(--muted); margin-left: auto; }
details.qa { border: 1px solid var(--border); border-radius: 10px; margin: 0 0 10px; background: var(--surface); }
details.qa[open] { border-color: var(--accent); }
details.qa summary { cursor: pointer; list-style: none; display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; font-weight: 560; }
details.qa summary::-webkit-details-marker { display: none; }
details.qa summary::after { content: "+"; margin-left: auto; color: var(--muted); font-weight: 400; font-size: 20px; line-height: 1; }
details.qa[open] summary::after { content: "−"; }
.q-tag { flex: none; width: 24px; height: 24px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-size: 13px; font-weight: 700; display: grid; place-items: center; margin-top: 1px; }
.ans { padding: 0 16px 6px 52px; }
details.qa.flash { animation: flash 1.2s ease-out; }
@keyframes flash { from { box-shadow: 0 0 0 4px var(--accent-soft); } to { box-shadow: none; } }

/* Dashboards */
.dash { max-width: 1280px; margin: 0 auto; padding: 24px 16px 64px; }
.dash h1 { font-size: 26px; margin-bottom: 6px; }
.lede { color: var(--muted); max-width: 920px; font-size: 15px; }
.grid { display: grid; gap: 16px; margin-bottom: 16px; }
.g-main { grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); }
.g-main .col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.g3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.g2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.g-notes { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); align-items: start; }
h2.sec { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; font-size: 16px; margin: 8px 0 0; padding: 8px 12px; border: 0; border-radius: 8px; background: var(--accent-soft); color: var(--accent); }
.g3 + .grid, h2.sec + .grid { margin-top: 0; }
.dash > h2.sec { margin: 8px 0 16px; }
.sec-num { font-weight: 750; }
.sec-note { font-size: 13px; font-weight: 400; color: var(--muted); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px 12px; box-shadow: var(--shadow); min-width: 0; }
.card-h { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
.card-h h3 { margin: 0; font-size: 15px; line-height: 1.35; }
.card-h p { margin: 2px 0 0; font-size: 13px; color: var(--muted); line-height: 1.4; }
.card-h button { margin-left: auto; flex: none; font-size: 12px; padding: 3px 9px; }
.card-b { min-height: 40px; }
.card-b svg { display: block; overflow: visible; width: 100%; height: auto; }
.card .caveat { font-size: 12.5px; color: var(--s2); margin: 6px 0 0; }
.card .table-wrap { margin: 0; }
.card table { font-size: 13px; }
.card th, .card td { padding: 5px 10px; }
.empty { color: var(--muted); font-size: 14px; padding: 16px 0; }
.note-box { background: var(--quote); border: 1px solid var(--border); border-radius: 12px; padding: 14px 18px; font-size: 14px; }
.note-box h3 { margin: 0 0 8px; font-size: 15px; }
.note-box li { margin: 4px 0; }
.note-box .small, .static-note { font-size: 12.5px; color: var(--muted); margin: 6px 0 0; }
.kpis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.kpi { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; }
.kpi.hero { grid-column: 1 / -1; }
.kpi .v { font-size: 26px; font-weight: 650; line-height: 1.15; font-variant-numeric: tabular-nums; }
.kpi.hero .v { font-size: 44px; }
.kpi .v small { font-size: 14px; font-weight: 500; color: var(--muted); }
.kpi .l { font-size: 12.5px; color: var(--muted); line-height: 1.35; }
.req-table td:first-child { white-space: nowrap; }
.req-table a { color: var(--accent); }
.sheet-group { margin-top: 24px; }
.sheet-group > h2 { font-size: 18px; margin: 0 0 12px; padding: 0; border: 0; }
.sheet-group .grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr)); }
.tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); margin-right: 6px; vertical-align: 1px; }

/* Chart marks */
.m1 { fill: var(--s1); }
.m2 { fill: var(--s2); }
.ln { fill: none; stroke: var(--s1); stroke-width: 2; }
.dot { fill: var(--s1); stroke: var(--surface); stroke-width: 2; }
.lbl { fill: var(--text); font-size: 12px; }
.val { fill: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; stroke-linejoin: round; }
.val tspan.b { fill: var(--text); font-weight: 650; }
.axis { fill: var(--muted); font-size: 11px; }
.gridln { stroke: var(--grid); stroke-width: 1; }
.ref { stroke: var(--ref); stroke-width: 1.5; stroke-dasharray: 4 3; }
.reflbl { fill: var(--ref); font-size: 11px; }
.hit { cursor: default; }
.hit.click { cursor: pointer; }
.hit:hover path, .hit:hover rect.cell { filter: brightness(1.08); }
.hit.click:hover .lbl { text-decoration: underline; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12.5px; color: var(--muted); margin: 0 0 6px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.legend .ramp { width: 72px; background: linear-gradient(90deg, #cde2fb, #3987e5, #0d366b); }
#tip {
  position: fixed; z-index: 50; pointer-events: none; max-width: 280px;
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: 8px 10px; font-size: 13px; line-height: 1.45;
  box-shadow: 0 4px 16px rgba(0,0,0,.14);
}
#tip b { font-weight: 650; }
#tip .t { font-weight: 650; margin-bottom: 2px; }

@media (max-width: 1000px) {
  .g-main, .g3, .g2, .g-notes { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; padding-top: 16px; }
  .toc { position: static; max-height: none; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; }
  .toc ol { display: flex; flex-wrap: wrap; gap: 4px; }
  .toc a { border: 1px solid var(--border); padding: 3px 10px; }
  article { padding: 20px 16px; }
  .brand { display: none; }
  .ans { padding-left: 16px; }
  .filters label { flex: 1 1 140px; }
  .filters select { max-width: none; }
  .dash h1 { font-size: 22px; }
}
@media print {
  header, .toc, .qa-tools, .card-h button { display: none; }
  [role="tabpanel"][hidden] { display: block; }
  .layout { display: block; }
  details.qa .ans { display: block; }
}
</style>
</head>
<body>
<header>
  <div class="bar">
    <span class="brand">DDOT FY26 Permit Approvals</span>
    <div role="tablist" aria-label="Views">{{TABS}}</div>
    <button type="button" class="theme-btn" id="theme-btn" aria-label="Toggle dark mode">◐</button>
  </div>
  <div class="filters" id="filters" hidden></div>
</header>
<main>
{{PANELS}}
</main>
<script type="application/json" id="permit-data">{{DATA}}</script>
<script src="app.js"></script>
<script>
(function () {
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  // ------------------------------------------------------------------ router
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  function show(id, targetId) {
    let panel;
    tabs.forEach(t => {
      const on = t.dataset.tab === id;
      t.setAttribute('aria-selected', on);
      t.tabIndex = on ? 0 : -1;
      const p = document.getElementById('panel-' + t.dataset.tab);
      p.hidden = !on;
      if (on) panel = p;
    });
    const isData = 'dash' in panel.dataset;
    document.getElementById('filters').hidden = !isData;
    if (isData) window.PermitDashboards.show(id, panel);
    store.set('prep-tab', id);
    // Look the target up after showing: dashboard panels are only built when first opened.
    const scrollTarget = targetId && document.getElementById(targetId);
    if (scrollTarget) scrollTarget.scrollIntoView();
    else window.scrollTo(0, 0);
    updateActive();
  }

  function route() {
    const hash = decodeURIComponent(location.hash.slice(1));
    const saved = store.get('prep-tab');
    if (!hash) return show(tabs.some(t => t.dataset.tab === saved) ? saved : tabs[0].dataset.tab);
    const tab = tabs.find(t => hash === t.dataset.tab || hash.startsWith(t.dataset.tab + '-'));
    if (tab) show(tab.dataset.tab, hash);
  }

  tabs.forEach((t, i) => {
    t.addEventListener('click', () => { history.pushState(null, '', '#' + t.dataset.tab); show(t.dataset.tab); });
    t.addEventListener('keydown', e => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus(); n.click();
    });
  });
  window.addEventListener('popstate', route);

  // Scroll-spy for the section nav.
  function updateActive() {
    const panel = document.querySelector('[role="tabpanel"]:not([hidden])');
    if (!panel) return;
    let current = null;
    panel.querySelectorAll('h2[id]').forEach(h => { if (h.getBoundingClientRect().top < 120) current = h.id; });
    panel.querySelectorAll('.toc a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + current));
  }
  window.addEventListener('scroll', updateActive, { passive: true });

  // Q&A tools.
  const cards = [...document.querySelectorAll('details.qa')];
  const search = document.getElementById('qa-search');
  const count = document.getElementById('qa-count');
  if (search) {
    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      let shown = 0;
      cards.forEach(c => {
        const hit = !q || c.textContent.toLowerCase().includes(q);
        c.hidden = !hit;
        if (hit) shown++;
      });
      count.textContent = q ? `${shown} of ${cards.length} questions` : `${cards.length} questions`;
    });
    document.querySelector('.qa-tools').addEventListener('click', e => {
      const act = e.target.dataset && e.target.dataset.act;
      if (act === 'expand') cards.forEach(c => { if (!c.hidden) c.open = true; });
      if (act === 'collapse') cards.forEach(c => c.open = false);
      if (act === 'random') {
        const pool = cards.filter(c => !c.hidden);
        if (!pool.length) return;
        cards.forEach(c => c.open = false);
        const pick = pool[Math.floor(Math.random() * pool.length)];
        pick.scrollIntoView({ block: 'center' });
        pick.classList.remove('flash'); void pick.offsetWidth; pick.classList.add('flash');
        pick.querySelector('summary').focus();
      }
    });
  }

  // Theme toggle.
  const root = document.documentElement;
  const saved = store.get('prep-theme');
  if (saved) root.dataset.theme = saved;
  document.getElementById('theme-btn').addEventListener('click', () => {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    store.set('prep-theme', root.dataset.theme);
  });

  route();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
