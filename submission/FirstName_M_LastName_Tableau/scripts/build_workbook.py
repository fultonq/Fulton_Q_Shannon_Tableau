"""Generate the Tableau workbook (.twb) and packaged workbook (.twbx).

The workbook is written as Tableau XML so it can be rebuilt from the data
without Tableau Desktop. It connects to data/fy26_new_issued_permits.csv
(a text-file connection) and contains:

  1. Overall Avg Business Days          - KPI: average business days to approve
  2. Avg Days by Permit Type             - by permit type category (work focus)
  3. Lead Free DC vs All Other           - the segment that splits the data most
  4. Avg Days by Applicant               - by applicant/utility group
  5. Approval Time Distribution          - permits per business-day band
  6. Trend by Application Month          - average by month of application
  7. Avg Days by Ward                    - geography
  8. Approval vs Issuance by Applicant   - approval stage vs payment/issuance stage
  Dashboard: FY26 Permit Approval Times

Usage:  python build_workbook.py
"""
from __future__ import annotations

import shutil
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "fy26_new_issued_permits.csv"
OUT_DIR = ROOT / "workbook"
WB_NAME = "DDOT_FY26_Permit_Approval_Times"
DATA_SUBDIR = "Data/permits"          # where the CSV lives relative to the .twb / inside the .twbx

DS = "federated.0fy26permits0approval0times"
CONN = "textscan.0fy26permits0csv0connection0"
DS_CAPTION = "FY26 New Issued Permits"
Q = f"[{DS}]"

SEG_CSV = ROOT / "data" / "segment_comparison.csv"
SEG_DS = "federated.0segment0comparison0vs0average"
SEG_CONN = "textscan.0segment0comparison0csv0conn00"
SEG_CAPTION = "Segment Comparison vs FY26 Average"
CAPTION_OF = {DS: DS_CAPTION, SEG_DS: SEG_CAPTION}

BLUE, ORANGE, GREY = "#4e79a7", "#f28e2b", "#bab0ac"

# ----------------------------------------------------------------------------- columns

DATETIME_COLS = {"ApplicationDate", "AssignedDate", "LastApprovalDate", "IssueDate", "EffectiveDate", "ExpirationDate"}
DATE_COLS = {"ApplicationMonth", "IssueMonth"}
INT_COLS = {"OBJECTID", "TrackingNumber", "DaysToAssign", "DaysToApprove", "DaysToIssue", "BusDaysToAssign",
            "BusDaysToApprove", "BusDaysApproveToIssue", "BusDaysToIssue", "SameDayApproval", "LineItemCount"}
REAL_COLS = {"TotalFee", "PermitFee", "Latitude", "Longitude",
             # segment comparison source
             "PctOfScope", "AvgBusDaysToApprove", "MedianBusDaysToApprove", "P25", "P75", "ScopeAverage",
             "DiffFromAverage", "PctDiffFromAverage", "AvgBusDaysToIssue"}
INT_COLS |= {"Permits"}
FORMATS = {"DiffFromAverage": "n+#,##0.0;-#,##0.0", "PctDiffFromAverage": "p+0%;-0%", "PctOfScope": "p0.0%",
           "AvgBusDaysToApprove": "n#,##0.0", "MedianBusDaysToApprove": "n#,##0.0", "ScopeAverage": "n#,##0.0",
           "AvgBusDaysToIssue": "n#,##0.0", "Permits": "n#,##0"}

CAPTIONS = {
    "BusDaysToApprove": "Business Days to Approve",
    "BusDaysToIssue": "Business Days to Issue",
    "BusDaysToAssign": "Business Days to Assign",
    "BusDaysApproveToIssue": "Business Days Approval to Issue",
    "WorkFocus": "Permit Type Category",
    "PermitCategory": "Work Type (TOPS flags)",
    "ApplicantGroup": "Applicant Group",
    "LeadFreeDC": "Lead Free DC Program",
    "ApprovalBucket": "Approval Time Band",
    "ApplicationMonth": "Application Month",
    "IssueMonth": "Issue Month",
    "ReviewedByPublicSpaceCommittee": "Public Space Committee Review",
    "DiffFromAverage": "Difference from Average (business days)",
    "PctDiffFromAverage": "% Difference from Average",
    "AvgBusDaysToApprove": "Segment Avg Business Days to Approve",
    "MedianBusDaysToApprove": "Segment Median Business Days to Approve",
    "ScopeAverage": "Comparison Average",
    "AvgBusDaysToIssue": "Segment Avg Business Days to Issue",
    "Flag": "Difference vs Average",
}

REMOTE_TYPE = {"integer": 20, "real": 5, "string": 129, "date": 133, "datetime": 135}


def col_type(name: str) -> str:
    if name in DATETIME_COLS:
        return "datetime"
    if name in DATE_COLS:
        return "date"
    if name in INT_COLS:
        return "integer"
    if name in REAL_COLS:
        return "real"
    return "string"


def role(name: str) -> tuple[str, str]:
    t = col_type(name)
    if t in ("integer", "real") and name not in {"OBJECTID", "TrackingNumber"}:
        return "measure", "quantitative"
    if t in ("date", "datetime"):
        return "dimension", "ordinal"
    if t == "integer":
        return "dimension", "ordinal"
    return "dimension", "nominal"


# Calculated fields: name -> (caption, formula, format)
CALCS = {
    "Calc_AvgApprove": ("Avg Business Days to Approve", "AVG([BusDaysToApprove])", "n#,##0.0"),
    "Calc_MedianApprove": ("Median Business Days to Approve", "MEDIAN([BusDaysToApprove])", "n#,##0.0"),
    "Calc_AvgIssue": ("Avg Business Days to Issue", "AVG([BusDaysToIssue])", "n#,##0.0"),
    "Calc_AvgApproveToIssue": ("Avg Business Days Approval to Issue", "AVG([BusDaysApproveToIssue])", "n#,##0.0"),
    "Calc_Permits": ("Permits", "COUNTD([OBJECTID])", "n#,##0"),
    "Calc_PctSameDay": ("% Approved Same Day", "AVG([SameDayApproval])", "p0.0%"),
    "Calc_PctOver60": ("% Over 60 Business Days",
                       "SUM(IIF([BusDaysToApprove] > 60, 1, 0)) / COUNT([BusDaysToApprove])", "p0.0%"),
    "Calc_PctOfPermits": ("% of Permits", "COUNTD([OBJECTID]) / TOTAL(COUNTD([OBJECTID]))", "p0.0%"),
}
CALC_DEPENDS = {
    "Calc_AvgApprove": ["BusDaysToApprove"], "Calc_MedianApprove": ["BusDaysToApprove"],
    "Calc_AvgIssue": ["BusDaysToIssue"], "Calc_AvgApproveToIssue": ["BusDaysApproveToIssue"],
    "Calc_Permits": ["OBJECTID"], "Calc_PctSameDay": ["SameDayApproval"], "Calc_PctOver60": ["BusDaysToApprove"],
    "Calc_PctOfPermits": ["OBJECTID"],
}


def a(v) -> str:
    return quoteattr(str(v))


def guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def base_column_xml(name: str) -> str:
    r, t = role(name)
    cap = f" caption={a(CAPTIONS[name])}" if name in CAPTIONS else ""
    if name in FORMATS:
        cap += f" default-format={a(FORMATS[name])}"
    return f"<column{cap} datatype={a(col_type(name))} name={a(f'[{name}]')} role={a(r)} type={a(t)} />"


def calc_column_xml(name: str) -> str:
    cap, formula, fmt = CALCS[name]
    return (f"<column caption={a(cap)} datatype='real' default-format={a(fmt)} name={a(f'[{name}]')} "
            f"role='measure' type='quantitative'><calculation class='tableau' formula={a(formula)} /></column>")


# ----------------------------------------------------------------------------- datasource

def datasource_xml(columns: list[str], ds: str = DS, conn: str = CONN, caption: str = DS_CAPTION,
                   filename: str = "fy26_new_issued_permits.csv", calcs_on: bool = True, style: str = "") -> str:
    stem = filename[:-4]
    rel_cols = "\n".join(
        f"            <column datatype={a(col_type(c))} name={a(c)} ordinal={a(i)} />" for i, c in enumerate(columns))
    meta = []
    for i, c in enumerate(columns):
        t = col_type(c)
        agg = "Sum" if t in ("integer", "real") else ("Year" if t in ("date", "datetime") else "Count")
        meta.append(f"""          <metadata-record class='column'>
            <remote-name>{escape(c)}</remote-name>
            <remote-type>{REMOTE_TYPE[t]}</remote-type>
            <local-name>[{escape(c)}]</local-name>
            <parent-name>[{escape(filename)}]</parent-name>
            <remote-alias>{escape(c)}</remote-alias>
            <ordinal>{i}</ordinal>
            <local-type>{t}</local-type>
            <aggregation>{agg}</aggregation>
            <contains-null>true</contains-null>
          </metadata-record>""")
    cols = "\n".join("      " + base_column_xml(c) for c in columns)
    calcs = "\n".join("      " + calc_column_xml(c) for c in CALCS) if calcs_on else ""
    return f"""    <datasource caption={a(caption)} inline='true' name={a(ds)} version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption={a(stem)} name={a(conn)}>
            <connection class='textscan' directory={a(DATA_SUBDIR)} filename={a(filename)} password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection={a(conn)} name={a(filename)} table={a(f"[{stem}#csv]")} type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
{rel_cols}
          </columns>
        </relation>
        <metadata-records>
{chr(10).join(meta)}
        </metadata-records>
      </connection>
      <aliases enabled='yes' />
{cols}
{calcs}
      <layout dim-ordering='alphabetic' dim-percentage='0.5' measure-percentage='0.4' measure-ordering='alphabetic' show-structure='true' />{style}
      <semantic-values>
        <semantic-value key='[Country].[Name]' value='&quot;United States&quot;' />
      </semantic-values>
    </datasource>"""


FLAG_COLORS = {"Meaningfully slower": "#f28e2b", "Meaningfully faster": "#4e79a7", "Within 7 days of average": "#bab0ac"}


def seg_style() -> str:
    maps = "\n".join(f"""            <map to={a(col)}>
              <bucket>&quot;{escape(k)}&quot;</bucket>
            </map>""" for k, col in FLAG_COLORS.items())
    return f"""
      <style>
        <style-rule element='mark'>
          <encoding attr='color' field='[none:Flag:nk]' type='palette'>
{maps}
          </encoding>
        </style-rule>
      </style>"""


# ----------------------------------------------------------------------------- worksheets

class Field:
    """A field placed on a shelf: base column or calc plus its derivation."""

    def __init__(self, column: str, derivation: str = "None", kind: str = "nk", ds: str = DS):
        self.column, self.derivation, self.kind, self.ds = column, derivation, kind, ds

    @property
    def is_calc(self) -> bool:
        return self.column in CALCS

    @property
    def prefix(self) -> str:
        return {"None": "none", "Avg": "avg", "Sum": "sum", "Min": "min", "User": "usr",
                "Month-Trunc": "tmn"}[self.derivation]

    @property
    def instance(self) -> str:
        return f"[{self.prefix}:{self.column}:{self.kind}]"

    @property
    def ref(self) -> str:
        return f"[{self.ds}].{self.instance}"

    def instance_xml(self) -> str:
        t = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[self.kind]
        return (f"<column-instance column={a(f'[{self.column}]')} derivation={a(self.derivation)} "
                f"name={a(self.instance)} pivot='key' type={a(t)} />")


def dim(c: str) -> Field:
    return Field(c, "None", "nk")


def calc(c: str) -> Field:
    return Field(c, "User", "qk")


def sdim(c: str) -> Field:
    return Field(c, "None", "nk", SEG_DS)


def ssum(c: str) -> Field:
    return Field(c, "Sum", "qk", SEG_DS)


def run(text: str, **attrs) -> str:
    at = "".join(f" {k.replace('_', '-')}={a(v)}" for k, v in attrs.items())
    return f"<run{at}>{escape(text)}</run>"


def worksheet_xml(name: str, title: str, *, rows: list[Field] = (), cols: list[Field] = (), mark: str = "Bar",
                  text: list[Field] = (), color: Field | None = None, tooltip: list[Field] = (),
                  sort: tuple[Field, Field, str] | None = None, mark_color: str | None = BLUE,
                  labels: bool = True, label_runs: list[str] | None = None, fit: str | None = None,
                  exclude=None, nest: bool = False, mv_on_cols: bool = False,
                  measure_values: list[Field] = (), header_widths: dict[str, int] | None = None) -> str:
    excludes = exclude if isinstance(exclude, list) else ([exclude] if exclude else [])
    fields = list(rows) + list(cols) + list(text) + list(tooltip) + ([color] if color else []) + list(measure_values)
    fields += [ef for ef, _ in excludes]
    ds = fields[0].ds
    if sort:
        fields += [sort[1]]
    # Dependencies: base columns, calcs (and the base columns they reference), then column instances.
    base, calcs, inst = {}, {}, {}
    for f in fields:
        inst[f.instance] = f
        if f.is_calc:
            calcs[f.column] = f
            for d in CALC_DEPENDS[f.column]:
                base[d] = True
        else:
            base[f.column] = True
    deps = [base_column_xml(c) for c in base] + [calc_column_xml(c) for c in calcs] + \
           [f.instance_xml() for f in sorted(inst.values(), key=lambda f: f.instance)]
    deps_xml = "\n".join("            " + d for d in deps)

    filter_xml = ""
    for ef, member in excludes:
        lvl = ef.instance
        filter_xml += (f"\n          <filter class='categorical' column={a(ef.ref)}>"
                      f"\n            <groupfilter function='except' user:ui-domain='database' "
                      f"user:ui-enumeration='exclusive' user:ui-marker='enumerate'>"
                      f"\n              <groupfilter function='level-members' level={a(lvl)} />"
                      f"\n              <groupfilter function='member' level={a(lvl)} member={a(chr(34) + member + chr(34))} />"
                      f"\n            </groupfilter>\n          </filter>")
    sort_xml = ""
    if sort:
        target, using, direction = sort
        sort_xml = (f"\n          <sort class='computed' column={a(target.ref)} direction={a(direction)} "
                    f"using={a(using.ref)} />")

    slices_xml = ("\n          <slices>" + "".join(f"\n            <column>{escape(ef.ref)}</column>" for ef, _ in excludes)
                  + "\n          </slices>") if excludes else ""
    mv_text = ""
    color_ref = color.ref if color else None
    if measure_values:
        mn = f"[{ds}].[:Measure Names]"
        members = "".join(
            f"\n              <groupfilter function='member' level='[:Measure Names]' member={a(chr(34) + f.ref + chr(34))} />"
            for f in measure_values)
        filter_xml += (f"\n          <filter class='categorical' column={a(mn)}>"
                       f"\n            <groupfilter function='union' user:op='manual'>{members}"
                       f"\n            </groupfilter>\n          </filter>")
        slices_xml = f"\n          <slices>\n            <column>{escape(mn)}</column>\n          </slices>"
        if mv_on_cols:
            color_ref = mn
        mv_text = f"[{ds}].[Multiple Values]"

    enc = []
    if color_ref:
        enc.append(f"<color column={a(color_ref)} />")
    if mv_text:
        enc.append(f"<text column={a(mv_text)} />")
    for f in text:
        enc.append(f"<text column={a(f.ref)} />")
    for f in tooltip:
        enc.append(f"<tooltip column={a(f.ref)} />")
    enc_xml = ("\n              <encodings>\n" + "\n".join("                " + e for e in enc) +
               "\n              </encodings>") if enc else ""

    custom_label = ""
    if label_runs:
        custom_label = ("\n              <customized-label>\n                <formatted-text>\n" +
                        "\n".join("                  " + r for r in label_runs) +
                        "\n                </formatted-text>\n              </customized-label>")

    mark_rules = []
    if mark_color and not color_ref:
        mark_rules.append(f"<format attr='mark-color' value={a(mark_color)} />")
    if labels:
        mark_rules.append("<format attr='mark-labels-show' value='true' />")
    pane_style = ""
    if mark_rules:
        pane_style = ("\n              <style>\n                <style-rule element='mark'>\n" +
                      "\n".join("                  " + r for r in mark_rules) +
                      "\n                </style-rule>\n              </style>")

    def shelf(fs: list[Field]) -> str:
        if not fs:
            return ""
        return fs[0].ref if len(fs) == 1 else "(" + (" / " if nest else " + ").join(f.ref for f in fs) + ")"

    table_style_xml = "<style />"
    if header_widths:
        hw = "\n".join(f"            <format attr='width' field={a(ref.replace('{ds}', f'[{ds}]'))} value='{px}' />"
                        for ref, px in header_widths.items())
        table_style_xml = (f"<style>\n          <style-rule element='header'>\n{hw}\n"
                           f"          </style-rule>\n        </style>")
    rows_s, cols_s = shelf(list(rows)), shelf(list(cols))
    if measure_values and mv_on_cols:
        cols_s = f"[{ds}].[Multiple Values]"
    elif measure_values:
        rows_s = f"[{ds}].[:Measure Names]"
    rows_xml = f"<rows>{escape(rows_s)}</rows>" if rows_s else "<rows />"
    cols_xml = f"<cols>{escape(cols_s)}</cols>" if cols_s else "<cols />"

    table_style = ""
    if fit:
        table_style = f"""
          <style-rule element='table'>
            <format attr='{fit}' value='true' />
          </style-rule>"""

    return f"""    <worksheet name={a(name)}>
      <layout-options>
        <title>
          <formatted-text>
            {run(title, bold='true', fontsize='12')}
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption={a(CAPTION_OF[ds])} name={a(ds)} />
          </datasources>
          <datasource-dependencies datasource={a(ds)}>
{deps_xml}
          </datasource-dependencies>{filter_xml}{sort_xml}{slices_xml}
          <aggregation value='true' />
        </view>
        {table_style_xml}
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class={a(mark)} />{enc_xml}{custom_label}{pane_style}
          </pane>
        </panes>
        {rows_xml}
        {cols_xml}
      </table>
    </worksheet>"""


AVG = calc("Calc_AvgApprove")
MED = calc("Calc_MedianApprove")
PERMITS = calc("Calc_Permits")
ISSUE = calc("Calc_AvgIssue")
A2I = calc("Calc_AvgApproveToIssue")
SAME = calc("Calc_PctSameDay")
OVER60 = calc("Calc_PctOver60")
PCT = calc("Calc_PctOfPermits")
STD_TIPS = [PERMITS, MED, ISSUE, OVER60]


def lt(f: Field) -> str:
    """A field reference inside a customized label."""
    return f"&lt;{f.ref}&gt;"


def kpi_runs() -> list[str]:
    def r(text, **kw):
        return run(text, **kw)

    nl = "<run>Æ&#10;</run>"
    return [
        r("Average business days to approve", fontsize="11", fontcolor="#555555"), nl,
        f"<run bold='true' fontcolor={a(BLUE)} fontsize='36'>{lt(AVG)}</run>", nl,
        r("Median ", fontsize="10", fontcolor="#555555"), f"<run bold='true' fontsize='10'>{lt(MED)}</run>",
        r("   |   Permits ", fontsize="10", fontcolor="#555555"), f"<run bold='true' fontsize='10'>{lt(PERMITS)}</run>", nl,
        r("Same-day approvals ", fontsize="10", fontcolor="#555555"), f"<run bold='true' fontsize='10'>{lt(SAME)}</run>",
        r("   |   Over 60 days ", fontsize="10", fontcolor="#555555"), f"<run bold='true' fontsize='10'>{lt(OVER60)}</run>", nl,
        r("Avg business days application to issuance ", fontsize="10", fontcolor="#555555"),
        f"<run bold='true' fontsize='10'>{lt(ISSUE)}</run>",
    ]


SHEETS = {
    "1. Overall Avg Business Days": dict(
        title="FY26 overall: new permits issued in FY26", mark="Text",
        measure_values=[AVG, MED, PERMITS, SAME, OVER60, ISSUE], labels=False, mark_color=None,
        header_widths={"{ds}.[:Measure Names]": 300}),
    "2. Avg Days by Permit Type": dict(
        title="Average business days to approve by permit type category",
        rows=[dim("WorkFocus")], cols=[AVG], text=[AVG], tooltip=STD_TIPS,
        sort=(dim("WorkFocus"), AVG, "DESC"), header_widths={"{ds}.[none:WorkFocus:nk]": 200}),
    "3. Lead Free DC vs All Other": dict(
        title="DC Water Lead Free DC permits vs. all other permits",
        rows=[dim("LeadFreeDC")], cols=[AVG], text=[AVG], tooltip=STD_TIPS, color=dim("LeadFreeDC"),
        sort=(dim("LeadFreeDC"), AVG, "DESC")),
    "4. Avg Days by Applicant": dict(
        title="Avg business days to approve by applicant group",
        rows=[dim("ApplicantGroup")], cols=[AVG], text=[AVG], tooltip=STD_TIPS,
        sort=(dim("ApplicantGroup"), AVG, "DESC")),
    "5. Approval Time Distribution": dict(
        title="How many permits fall in each approval-time band (business days)",
        cols=[dim("ApprovalBucket")], rows=[PERMITS], text=[PERMITS], tooltip=[PCT, AVG],
        exclude=(dim("ApprovalBucket"), "Not Approved"), sort=(dim("ApprovalBucket"), Field("BusDaysToApprove", "Min", "qk"), "ASC")),
    "6. Trend by Application Month": dict(
        title="Avg business days to approve by application month", mark="Line",
        cols=[Field("ApplicationMonth", "Month-Trunc", "qk")], rows=[AVG], tooltip=STD_TIPS,
        color=dim("LeadFreeDC"), labels=False),
    "7. Avg Days by Ward": dict(
        title="Average business days to approve by ward",
        cols=[dim("Ward")], rows=[AVG], text=[AVG], tooltip=STD_TIPS),
    "8. Approval vs Issuance by Applicant": dict(
        title="Where the time goes: approval vs. approval-to-issue stage",
        rows=[dim("ApplicantGroup")], measure_values=[AVG, A2I], mv_on_cols=True, tooltip=[PERMITS, ISSUE],
        sort=(dim("ApplicantGroup"), ISSUE, "DESC")),
    "9. Segments vs FY26 Average": dict(
        title="Segments 7+ business days from the FY26 average (43.8)",
        rows=[sdim("SegmentLabel")], cols=[ssum("DiffFromAverage")], text=[ssum("DiffFromAverage")], color=sdim("Flag"),
        tooltip=[ssum("Permits"), ssum("AvgBusDaysToApprove"), ssum("MedianBusDaysToApprove"), ssum("ScopeAverage")],
        exclude=[(sdim("Scope"), "Excluding Lead Free DC"), (sdim("Flag"), "Within 7 days of average")],
        sort=(sdim("SegmentLabel"), ssum("DiffFromAverage"), "DESC"),
        header_widths={"{ds}.[none:SegmentLabel:nk]": 290}),
    "10. Segments excl. Lead Free DC": dict(
        title="Excluding Lead Free DC: segments 7+ days from that average (19.5)",
        rows=[sdim("SegmentLabel")], cols=[ssum("DiffFromAverage")], text=[ssum("DiffFromAverage")], color=sdim("Flag"),
        tooltip=[ssum("Permits"), ssum("AvgBusDaysToApprove"), ssum("MedianBusDaysToApprove"), ssum("ScopeAverage")],
        exclude=[(sdim("Scope"), "All FY26 permits"), (sdim("Flag"), "Within 7 days of average")],
        sort=(sdim("SegmentLabel"), ssum("DiffFromAverage"), "DESC"),
        header_widths={"{ds}.[none:SegmentLabel:nk]": 290}),
    "11. Ward x Program Heatmap": dict(
        title="Avg business days by ward and program",
        mark="Square", rows=[dim("Ward")], cols=[dim("LeadFreeDC")], text=[AVG], color=AVG,
        tooltip=[PERMITS, MED], mark_color=None),
}


# ----------------------------------------------------------------------------- dashboard

class Ids:
    def __init__(self):
        self.n = 2

    def __call__(self) -> int:
        self.n += 1
        return self.n


def text_zone(ids: Ids, x, y, w, h, runs: list[str], fixed_px: int | None = None) -> str:
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    return (f"<zone{fixed} h='{h}' id='{ids()}' type-v2='text' w='{w}' x='{x}' y='{y}'>"
            f"<formatted-text>{''.join(runs)}</formatted-text></zone>")


def sheet_zone(ids: Ids, name: str, x, y, w, h, fixed_px: int | None = None) -> str:
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    return f"<zone{fixed} h='{h}' id='{ids()}' name={a(name)} w='{w}' x='{x}' y='{y}' />"


def flow(ids: Ids, param: str, x, y, w, h, children: list[str], fixed_px: int | None = None) -> str:
    inner = "\n".join(children)
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    return (f"<zone{fixed} h='{h}' id='{ids()}' param='{param}' type-v2='layout-flow' w='{w}' x='{x}' y='{y}'>\n"
            f"{inner}\n</zone>")


NL = "<run>Æ&#10;</run>"


def section(title: str, note: str) -> list[str]:
    return [run(title, bold="true", fontsize="13", fontcolor="#1f3b57"),
            run("   " + note, fontsize="9", fontcolor="#555555")]


def dashboard_xml() -> str:
    ids = Ids()
    W = 100000
    # Vertical bands in pixels (dashboard is 1300 px tall); each band gets a fixed height.
    HEIGHT = 1760
    bands = [("title", 75), ("guide", 50), ("s1h", 48), ("s1", 280), ("s2h", 48), ("s2", 290),
             ("s3h", 48), ("s3", 290), ("s4h", 48), ("s4", 430), ("insights", 153)]
    assert sum(px for _, px in bands) == HEIGHT
    ys, px_of, y = {}, {}, 0
    for i, (key, px) in enumerate(bands):
        h = 100000 - y if i == len(bands) - 1 else round(px * 100000 / HEIGHT)
        ys[key], px_of[key] = (y, h), px
        y += h

    def band(key):
        return ys[key]

    rows = []
    y0, h = band("title")
    rows.append(text_zone(ids, 0, y0, W, h, [
        run("Public Space Construction Permits: FY26 Average Business Days to Approve", bold="true", fontsize="20",
            fontcolor="#1f3b57"), NL,
        run("DDOT Public Space Division  |  Analytics, Assets, and Performance Branch  |  Source: DC GIS TOPS feed "
            "(MapServer/23), pulled Nov 2026", fontsize="9", fontcolor="#777777")], px_of["title"]))
    y0, h = band("guide")
    rows.append(text_zone(ids, 0, y0, W, h, [
        run("How to read this: ", bold="true", fontsize="9"),
        run("Scope is new permits (no renewals) applied for on or after Oct 1, 2025 and issued in FY26 "
            "(Oct 1, 2025 - Sep 30, 2026): 11,206 permits. Business days = days from application to final approval, "
            "excluding weekends and DC holidays (same-day approval = 0). Hover any mark for permit counts, median and "
            "days to issuance.", fontsize="9")], px_of["guide"]))

    def section_row(hkey, rkey, header_title, header_note, sheets: list[tuple[str, int]]):
        y0, h = band(hkey)
        rows.append(text_zone(ids, 0, y0, W, h, section(header_title, header_note), px_of[hkey]))
        y0, h = band(rkey)
        x, kids = 0, []
        for i, (name, w) in enumerate(sheets):
            w = W - x if i == len(sheets) - 1 else w
            kids.append(sheet_zone(ids, name, x, y0, w, h, 500 if name.startswith("1.") else None))
            x += w
        rows.append(flow(ids, "horz", 0, y0, W, h, kids, px_of[rkey]))

    section_row("s1h", "s1", "1. Overall performance",
                "The FY26 average, and how widely approval times are spread around it.",
                [("1. Overall Avg Business Days", 34000), ("5. Approval Time Distribution", 66000)])
    section_row("s2h", "s2", "2. Approval time by permit type category",
                "Permit type is derived from the line items on each permit. Lead service line replacements (DC Water's "
                "Lead Free DC program) are 84% of permits and drive the overall average.",
                [("2. Avg Days by Permit Type", 50000), ("3. Lead Free DC vs All Other", 50000)])
    section_row("s3h", "s3", "3. Other segments worth exploring",
                "Applicant, timing and stage of the process show where approval times are meaningfully different.",
                [("4. Avg Days by Applicant", 34000), ("6. Trend by Application Month", 33000),
                 ("8. Approval vs Issuance by Applicant", 33000)])
    section_row("s4h", "s4", "4. Where approval times are meaningfully different",
                "Segments with 30+ permits whose average is 7+ business days above (orange) or below (blue) the average. "
                "The middle chart removes Lead Free DC so program mix doesn't drive the result.",
                [("9. Segments vs FY26 Average", 37000), ("10. Segments excl. Lead Free DC", 37000),
                 ("11. Ward x Program Heatmap", 26000)])

    y0, h = band("insights")
    rows.append(text_zone(ids, 0, y0, W, h, [
        run("Key insights and next steps", bold="true", fontsize="12", fontcolor="#1f3b57"), NL,
        run("- Overall: 43.8 business days on average (median 39); only 3% are approved the same day and 24% take "
            "more than 60 business days.", fontsize="9"), NL,
        run("- Lead Free DC permits average 48.4 days vs. 19.5 for all other permits; most of the FY26 backlog is one "
            "program. Gas (10.0), water/sewer (19.1) and electric/telecom (25.2) utility work is approved much faster.",
            fontsize="9"), NL,
        run("- Washington Gas is approved in 11.5 days but waits 45 more days on average between approval and issuance "
            "(payment / pick-up stage), so its total time is similar to other groups.", fontsize="9"), NL,
        run("- Meaningfully slower (7+ days above average): Public Space Committee review (72.0), Q1-Q2 applications "
            "(69-71), Ward 3 (60.1), other excavation (57.8). Meaningfully faster: DC Water non-lead work (5.2), gas (10.0), "
            "single-line-item permits (14.2), Ward 8 (28.4).", fontsize="9"), NL,
        run("- Ward differences come from the Lead Free DC program (Ward 3: 68.9 vs. Ward 8: 30.2). For all other permits "
            "every ward is 15-24 days. Later months look faster partly because only permits issued by Sep 30 are "
            "included. Next: investigate the Lead Free DC queue by ward and the Q1-Q2 backlog.", fontsize="9")]))

    root = flow(ids, "vert", 0, 0, W, 100000, rows)
    return f"""  <dashboards>
    <dashboard name='FY26 Permit Approval Dashboard'>
      <style />
      <size maxheight='1760' maxwidth='1600' minheight='1760' minwidth='1200' sizing-mode='range' />
      <datasources />
      <zones>
        <zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>
{root}
        </zone>
      </zones>
      <devicelayouts>
        <devicelayout name='Tablet'>
          <size sizing-mode='automatic' />
        </devicelayout>
      </devicelayouts>
    </dashboard>
  </dashboards>"""


# ----------------------------------------------------------------------------- windows & assembly

def windows_xml() -> str:
    out = ["  <windows source-height='30'>"]
    for name in SHEETS:
        out.append(f"""    <window class='worksheet' name={a(name)}>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
          <strip size='31'>
            <card type='title' />
          </strip>
        </edge>
      </cards>
      <viewpoint>
        <zoom type='entire-view' />
      </viewpoint>
    </window>""")
    viewpoints = "\n".join(f"        <viewpoint name={a(n)}>\n          <zoom type='entire-view' />\n        </viewpoint>" for n in SHEETS)
    out.append(f"""    <window class='dashboard' maximized='true' name='FY26 Permit Approval Dashboard'>
      <viewpoints>
{viewpoints}
      </viewpoints>
      <active id='-1' />
      <device-preview>
        <device is-portrait='true' name='Generic Phone' type='Phone' />
      </device-preview>
    </window>""")
    out.append("  </windows>")
    return "\n".join(out)


def build_twb(columns: list[str], seg_columns: list[str]) -> str:
    sheets = "\n".join(worksheet_xml(n, **kw) for n, kw in SHEETS.items())
    return f"""<?xml version='1.0' encoding='utf-8' ?>
<!-- Generated by scripts/build_workbook.py -->
<workbook original-version='18.1' source-build='2023.3.0 (20233.23.1017.0948)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
{datasource_xml(columns)}
{datasource_xml(seg_columns, SEG_DS, SEG_CONN, SEG_CAPTION, SEG_CSV.name, calcs_on=False, style=seg_style())}
  </datasources>
  <worksheets>
{sheets}
  </worksheets>
{dashboard_xml()}
{windows_xml()}
</workbook>
"""


def main() -> None:
    columns = list(pd.read_csv(CSV, nrows=0).columns)
    xml = build_twb(columns, list(pd.read_csv(SEG_CSV, nrows=0).columns))

    OUT_DIR.mkdir(exist_ok=True)
    twb = OUT_DIR / f"{WB_NAME}.twb"
    twb.write_text(xml, encoding="utf-8")
    # Keep the CSV next to the .twb at the relative path the connection uses.
    data_dir = OUT_DIR / DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CSV, data_dir / CSV.name)
    shutil.copy2(SEG_CSV, data_dir / SEG_CSV.name)

    twbx = OUT_DIR / f"{WB_NAME}.twbx"
    with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(twb, twb.name)
        z.write(CSV, f"{DATA_SUBDIR}/{CSV.name}")
        z.write(SEG_CSV, f"{DATA_SUBDIR}/{SEG_CSV.name}")
    print(f"Wrote {twb}\nWrote {twbx}")


if __name__ == "__main__":
    main()
