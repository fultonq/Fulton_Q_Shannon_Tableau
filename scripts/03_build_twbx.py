"""Generate the packaged Tableau workbook (.twbx) from the prepared CSVs.

Usage: python3 03_build_twbx.py <project dir>

Writes <project dir>/FY26_Public_Space_Permit_Approvals.twbx (plus the unpacked .twb for inspection).
The XML layout mirrors workbooks saved by Tableau Desktop 2024.1 (legacy relation, no object graph),
which later Tableau Desktop versions open and upgrade on save.
"""
import csv, os, sys, zipfile
import xml.etree.ElementTree as ET

USER_NS = "http://www.tableausoftware.com/xml/user"
ET.register_namespace("user", USER_NS)
U = lambda a: f"{{{USER_NS}}}{a}"

DS = "federated.fy26permits0001"
DSQ = f"[{DS}]"
CONN = "textscan.fy26permits0001"
CSV_NAME = "permits_by_tracking_number.csv"
PKG_DIR = "Data/data"
NL = "Æ\n"  # Tableau's paragraph break inside formatted text

# ---------------------------------------------------------------- source columns
CSV_TYPES = {
    "TrackingNumber": "string", "PermitNumber": "string", "Status": "string", "NewOrRenewal": "string",
    "ApplicationDate": "date", "ApprovalDate": "date", "IssueDate": "date", "IssuedInFY26": "integer",
    "BusinessDaysToApprove_QA": "integer", "BusinessDaysToIssue_QA": "integer",
    "CalendarDaysToApprove": "integer", "WorkTypeFamily": "string", "PermitCategory": "string",
    "TypeDetailNames": "string", "NumWorkTypes": "integer", "ApplicantType": "string",
    "PermitteeName": "string", "ResubmissionRequested": "string", "PSCReview": "string",
    "NumBlockLocations": "integer", "LocationBucket": "string", "Ward": "string", "Quadrant": "string",
    "TotalFee": "real", "Latitude": "real", "Longitude": "real", "WorkLocation": "string",
}
REMOTE_TYPE = {"string": "129", "integer": "20", "real": "5", "date": "133"}
DEFAULT_AGG = {"string": "Count", "integer": "Sum", "real": "Sum", "date": "Year"}

# ---------------------------------------------------------------- calculations
def load_holidays(project):
    """Read the holiday dates (YYYY-MM-DD) from <project>/data/dc_holidays.csv, written by 02_prepare_permits.py.

    Using that file keeps the Tableau formula and the Python QA count on one holiday list.
    """
    with open(os.path.join(project, "data", "dc_holidays.csv"), newline="") as f:
        return [r["HolidayDate"] for r in csv.DictReader(f)]


HOLIDAYS = load_holidays(sys.argv[1])


def weekday_index(field):
    """Tableau expression counting weekdays from a fixed Sunday anchor to [field]; differences give weekdays elapsed."""
    d = f"DATEDIFF('day', #2023-01-01#, [{field}])"
    return f"5 * INT({d} / 7) + MIN({d} % 7, 5)"


def holidays_between(end_field):
    """Tableau expression counting HOLIDAYS after [ApplicationDate] and on or before [end_field]."""
    return " +\n".join(
        f"IIF(#{h}# > [ApplicationDate] AND #{h}# <= [{end_field}], 1, 0)" for h in HOLIDAYS)


# (internal id, caption, datatype, role, type, formula, default-format)
CALCS = [
    ("Calc_InScope", "In Scope (FY26 New Issued)", "boolean", "dimension", "nominal",
     '[NewOrRenewal] = "New"\nAND [ApplicationDate] >= #2025-10-01#\n'
     "AND [IssueDate] >= #2025-10-01#\nAND [IssueDate] <= #2026-09-30#", None),
    ("Calc_WkApp", "Weekday Index - Application", "integer", "measure", "quantitative",
     weekday_index("ApplicationDate"), None),
    ("Calc_WkApr", "Weekday Index - Approval", "integer", "measure", "quantitative",
     weekday_index("ApprovalDate"), None),
    ("Calc_WkIss", "Weekday Index - Issue", "integer", "measure", "quantitative",
     weekday_index("IssueDate"), None),
    ("Calc_HolApr", "Holidays - Application to Approval", "integer", "measure", "quantitative",
     holidays_between("ApprovalDate"), None),
    ("Calc_HolIss", "Holidays - Application to Issue", "integer", "measure", "quantitative",
     holidays_between("IssueDate"), None),
    ("Calc_BDApprove", "Business Days to Approve", "integer", "measure", "quantitative",
     "IF [Calc_InScope] THEN\n[Calc_WkApr] - [Calc_WkApp] - [Calc_HolApr]\nEND", None),
    ("Calc_BDIssue", "Business Days to Issue", "integer", "measure", "quantitative",
     "IF [Calc_InScope] AND NOT ISNULL([ApprovalDate]) THEN\n[Calc_WkIss] - [Calc_WkApp] - [Calc_HolIss]\nEND", None),
    ("Calc_QA", "QA Mismatch", "integer", "measure", "quantitative",
     "ABS([Calc_BDApprove] - [BusinessDaysToApprove_QA])", None),
    ("Calc_Band", "Approval Time Band", "string", "dimension", "nominal",
     'IF ISNULL([Calc_BDApprove]) THEN NULL\nELSEIF [Calc_BDApprove] = 0 THEN "Same day"\n'
     'ELSEIF [Calc_BDApprove] <= 5 THEN "1-5 days"\nELSEIF [Calc_BDApprove] <= 10 THEN "6-10 days"\n'
     'ELSEIF [Calc_BDApprove] <= 20 THEN "11-20 days"\nELSEIF [Calc_BDApprove] <= 40 THEN "21-40 days"\n'
     'ELSEIF [Calc_BDApprove] <= 60 THEN "41-60 days"\nELSE "61+ days" END', None),
    ("Calc_AvgApprove", "Avg Business Days to Approve", "real", "measure", "quantitative",
     "AVG([Calc_BDApprove])", "n#,##0.0;-#,##0.0"),
    ("Calc_MedApprove", "Median Business Days to Approve", "real", "measure", "quantitative",
     "MEDIAN([Calc_BDApprove])", "n#,##0;-#,##0"),
    ("Calc_AvgIssue", "Avg Business Days to Issue", "real", "measure", "quantitative",
     "AVG([Calc_BDIssue])", "n#,##0.0;-#,##0.0"),
    ("Calc_Permits", "Permits (measured)", "integer", "measure", "quantitative",
     "COUNTD(IF NOT ISNULL([Calc_BDApprove]) THEN [TrackingNumber] END)", "n#,##0;-#,##0"),
    ("Calc_PermitsScope", "Permits In Scope", "integer", "measure", "quantitative",
     "COUNTD(IF [Calc_InScope] THEN [TrackingNumber] END)", "n#,##0;-#,##0"),
    ("Calc_Overall", "Overall Avg (FIXED)", "real", "measure", "quantitative",
     "{ FIXED : AVG([Calc_BDApprove]) }", "n#,##0.0;-#,##0.0"),
    ("Calc_Diff", "Diff vs Overall", "real", "measure", "quantitative",
     "[Calc_AvgApprove] - AVG([Calc_Overall])", "n#,##0.0;-#,##0.0"),
    ("Calc_Pct10", "% Approved Within 10 Business Days", "real", "measure", "quantitative",
     "SUM(IIF([Calc_BDApprove] <= 10, 1, 0)) / COUNT([Calc_BDApprove])", "p0%"),
    ("Calc_SumQA", "QA Mismatch Total", "integer", "measure", "quantitative",
     "SUM([Calc_QA])", None),
    ("Calc_Speed", "Speed vs Overall", "string", "measure", "nominal",
     'IF [Calc_Diff] <= -5 THEN "Faster than overall"\nELSEIF [Calc_Diff] >= 5 THEN "Slower than overall"\n'
     'ELSE "Near overall" END', None),
]
CALC_BY_ID = {c[0]: c for c in CALCS}


# ---------------------------------------------------------------- column-instance helpers
def dim(field):
    """Column-instance tuple for a discrete dimension on a source/calc field."""
    return ("none", field, "nk", "None", "nominal")


def usr(calc, kind="qk"):
    """Column-instance tuple for an aggregate calculation (kind "qk" = continuous measure, "nk" = discrete)."""
    return ("usr", calc, kind, "User", "quantitative" if kind == "qk" else "nominal")


KPI_LABELS = [
    (("usr", "Calc_AvgApprove", "qk", "User", "quantitative"), "Average business days to approve"),
    (("usr", "Calc_MedApprove", "qk", "User", "quantitative"), "Median business days to approve"),
    (("usr", "Calc_Pct10", "qk", "User", "quantitative"), "% approved within 10 business days"),
    (("usr", "Calc_AvgIssue", "qk", "User", "quantitative"), "Avg business days to issue (incl. applicant payment)"),
    (("usr", "Calc_Permits", "qk", "User", "quantitative"), "Permits measured"),
    (("usr", "Calc_PermitsScope", "qk", "User", "quantitative"), "Permits in scope"),
    (("usr", "Calc_SumQA", "qk", "User", "quantitative"), "QA mismatches vs. Python check (should be 0)"),
]
KPI_MEASURES = [ci for ci, _ in KPI_LABELS]


def agg(prefix, field, deriv):
    """Column-instance tuple for an aggregated field, e.g. agg("avg", "Calc_Overall", "Avg")."""
    return (prefix, field, "qk", deriv, "quantitative")


def inst_name(ci):
    """Tableau column-instance name, e.g. [usr:Calc_AvgApprove:qk]."""
    return f"[{ci[0]}:{ci[1]}:{ci[2]}]"


def ref(ci):
    """Fully qualified column-instance reference, prefixed with the data source name."""
    return f"{DSQ}.{inst_name(ci)}"


def column_el(parent, field):
    """Declare a source column or calculation."""
    if field in CALC_BY_ID:
        cid, cap, dtype, role, typ, formula, fmt = CALC_BY_ID[field]
        attrs = {"caption": cap, "datatype": dtype, "name": f"[{cid}]", "role": role, "type": typ}
        if fmt:
            attrs["default-format"] = fmt
        c = ET.SubElement(parent, "column", attrs)
        ET.SubElement(c, "calculation", {"class": "tableau", "formula": formula})
    else:
        dtype = CSV_TYPES[field]
        role = "measure" if dtype in ("integer", "real") else "dimension"
        typ = "quantitative" if role == "measure" else ("ordinal" if dtype == "date" else "nominal")
        ET.SubElement(parent, "column", {"datatype": dtype, "name": f"[{field}]", "role": role, "type": typ})


def deps_of(field, acc):
    """Every source column / calc a field depends on (transitively)."""
    if field in acc:
        return acc
    acc.append(field)
    if field in CALC_BY_ID:
        formula = CALC_BY_ID[field][5]
        for name in list(CSV_TYPES) + list(CALC_BY_ID):
            if f"[{name}]" in formula:
                deps_of(name, acc)
    return acc


# ---------------------------------------------------------------- text helpers
def formatted_text(parent, runs):
    """Append a <formatted-text> element built from (text, style-attrs) runs."""
    ft = ET.SubElement(parent, "formatted-text")
    for text, style in runs:
        r = ET.SubElement(ft, "run", style or {})
        r.text = text
    return ft


def field_token(ci):
    """Field placeholder for use inside titles, labels, and tooltips."""
    return f"<{ref(ci)}>"


# ---------------------------------------------------------------- worksheet builder
def worksheet(parent, name, title, rows, cols, mark, encodings, sort=None, label_runs=None,
              show_labels=True, extra_instances=(), caption_runs=None, refline=None, mark_color=None,
              measure_names=()):
    """Append a worksheet, filtered to the FY26 scope, to parent.

    rows / cols are column instances for the shelves; encodings is a list of (kind, instance) pairs
    such as ("color", ci); sort = (sorted instance, sort-by instance, "ASC" | "DESC").
    refline = (axis instance, value instance, label): a per-table average line drawn at the value.
    measure_names builds a Measure Names / Measure Values text table of those measures.
    """
    if refline:
        encodings = encodings + [("lod", refline[1])]
    ws = ET.SubElement(parent, "worksheet", {"name": name})
    lo = ET.SubElement(ws, "layout-options")
    t = ET.SubElement(lo, "title")
    runs = [(title, {"bold": "true", "fontsize": "12"})]
    if caption_runs:
        runs += caption_runs
    formatted_text(t, runs)

    table = ET.SubElement(ws, "table")
    view = ET.SubElement(table, "view")
    dss = ET.SubElement(view, "datasources")
    ET.SubElement(dss, "datasource", {"caption": "FY26 Permits", "name": DS})

    instances = [c for c in rows + cols] + [ci for _, ci in encodings] + list(extra_instances) + list(measure_names)
    scope = dim("Calc_InScope")
    instances.append(scope)
    if sort:
        instances.append(sort[1])
    fields = []
    for ci in instances:
        deps_of(ci[1], fields)
    dd = ET.SubElement(view, "datasource-dependencies", {"datasource": DS})
    for f in sorted(fields, key=lambda f: (f in CALC_BY_ID, f)):
        column_el(dd, f)
    seen = set()
    for ci in instances:
        if inst_name(ci) in seen:
            continue
        seen.add(inst_name(ci))
        ET.SubElement(dd, "column-instance", {
            "column": f"[{ci[1]}]", "derivation": ci[3], "name": inst_name(ci),
            "pivot": "key", "type": ci[4]})

    # every sheet is limited to the FY26 scope
    flt = ET.SubElement(view, "filter", {"class": "categorical", "column": ref(scope)})
    ET.SubElement(flt, "groupfilter", {
        "function": "member", "level": inst_name(scope), "member": "true",
        U("ui-domain"): "database", U("ui-enumeration"): "inclusive", U("ui-marker"): "enumerate"})
    if measure_names:  # text table of several measures, labelled by their Measure Names aliases
        mn = ET.SubElement(view, "filter", {"class": "categorical", "column": f"{DSQ}.[:Measure Names]"})
        union = ET.SubElement(mn, "groupfilter", {"function": "union", U("op"): "manual"})
        for ci in measure_names:
            ET.SubElement(union, "groupfilter", {"function": "member", "level": "[:Measure Names]",
                                                 "member": f'"{ref(ci)}"'})
    if sort:
        ET.SubElement(view, "sort", {"class": "computed", "column": ref(sort[0]), "direction": sort[2],
                                     "using": ref(sort[1])})
    slices = ET.SubElement(view, "slices")
    ET.SubElement(slices, "column").text = ref(scope)
    if measure_names:
        ET.SubElement(slices, "column").text = f"{DSQ}.[:Measure Names]"
    ET.SubElement(view, "aggregation", {"value": "true"})

    ET.SubElement(table, "style")
    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane")
    pv = ET.SubElement(pane, "view")
    ET.SubElement(pv, "breakdown", {"value": "auto"})
    ET.SubElement(pane, "mark", {"class": mark})
    enc = ET.SubElement(pane, "encodings")
    for kind, ci in encodings:
        ET.SubElement(enc, kind, {"column": ref(ci)})
    if measure_names:
        ET.SubElement(enc, "text", {"column": f"{DSQ}.[Multiple Values]"})
    if refline:
        ET.SubElement(pane, "reference-line", {
            "axis-column": ref(refline[0]), "enable-instant-analytics": "true", "formula": "average",
            "id": "refline0", "label": refline[2], "label-type": "custom", "scope": "per-table",
            "value-column": ref(refline[1]), "z-order": "1"})
    if label_runs:
        cl = ET.SubElement(pane, "customized-label")
        formatted_text(cl, label_runs)
    if show_labels or mark_color:
        st = ET.SubElement(pane, "style")
        sr = ET.SubElement(st, "style-rule", {"element": "mark"})
        if mark_color:
            ET.SubElement(sr, "format", {"attr": "mark-color", "value": mark_color})
        if show_labels:
            ET.SubElement(sr, "format", {"attr": "mark-labels-show", "value": "true"})
    ET.SubElement(table, "rows").text = (f"{DSQ}.[:Measure Names]" if measure_names else
                                         " + ".join(ref(c) for c in rows) if len(rows) > 1 else
                                         (ref(rows[0]) if rows else ""))
    ET.SubElement(table, "cols").text = ("(" + " + ".join(ref(c) for c in cols) + ")") if len(cols) > 1 else (ref(cols[0]) if cols else "")
    return ws


# ---------------------------------------------------------------- dashboard builder
class Zones:
    """Creates dashboard zones with unique, sequential ids."""

    def __init__(self):
        """Start zone ids at 1."""
        self.next_id = 1

    def zone(self, parent, x, y, w, h, **attrs):
        """Append a zone at (x, y) sized w x h (units of 1/100000 of the dashboard)."""
        z = ET.SubElement(parent, "zone", {"h": str(h), "id": str(self.next_id), **attrs,
                                           "w": str(w), "x": str(x), "y": str(y)})
        self.next_id += 1
        return z

    def text(self, parent, x, y, w, h, runs, bg=None):
        """Append a text zone from formatted runs, with an optional background color."""
        z = self.zone(parent, x, y, w, h, **{"type-v2": "text"})
        formatted_text(z, runs)
        if bg:
            zs = ET.SubElement(z, "zone-style")
            ET.SubElement(zs, "format", {"attr": "background-color", "value": bg})
        return z


def build():
    """Build the workbook XML (data source, action, worksheets, dashboards, windows) and write the .twb and .twbx."""
    project = sys.argv[1]
    wb = ET.Element("workbook", {"original-version": "18.1", "source-build": "2024.1.3 (20241.24.0515.0324)",
                                 "source-platform": "win", "version": "18.1"})
    prefs = ET.SubElement(wb, "preferences")
    ET.SubElement(prefs, "preference", {"name": "ui.encoding.shelf.height", "value": "24"})
    ET.SubElement(prefs, "preference", {"name": "ui.shelf.height", "value": "26"})

    # ------------------------------------------------------------ data source
    dss = ET.SubElement(wb, "datasources")
    ds = ET.SubElement(dss, "datasource", {"caption": "FY26 Permits", "inline": "true", "name": DS,
                                           "version": "18.1"})
    conn = ET.SubElement(ds, "connection", {"class": "federated"})
    ncs = ET.SubElement(conn, "named-connections")
    nc = ET.SubElement(ncs, "named-connection", {"caption": "permits_by_tracking_number", "name": CONN})
    ET.SubElement(nc, "connection", {"class": "textscan", "directory": PKG_DIR, "filename": CSV_NAME,
                                     "password": "", "server": ""})
    rel = ET.SubElement(conn, "relation", {"connection": CONN, "name": CSV_NAME,
                                           "table": "[permits_by_tracking_number#csv]", "type": "table"})
    cols = ET.SubElement(rel, "columns", {"character-set": "UTF-8", "header": "yes", "locale": "en_US",
                                          "separator": ","})
    for i, (f, t) in enumerate(CSV_TYPES.items()):
        ET.SubElement(cols, "column", {"datatype": t, "name": f, "ordinal": str(i)})
    mrs = ET.SubElement(conn, "metadata-records")
    cap = ET.SubElement(mrs, "metadata-record", {"class": "capability"})
    for tag, val in [("remote-name", None), ("remote-type", "0"), ("parent-name", f"[{CSV_NAME}]"),
                     ("remote-alias", None), ("aggregation", "Count"), ("contains-null", "true")]:
        ET.SubElement(cap, tag).text = val
    attrs = ET.SubElement(cap, "attributes")
    for n, v in [("character-set", "UTF-8"), ("collation", "en_US"), ("field-delimiter", ","),
                 ("header-row", "true"), ("locale", "en_US"), ("single-char", "")]:
        ET.SubElement(attrs, "attribute", {"datatype": "string", "name": n}).text = f'"{v}"'
    for i, (f, t) in enumerate(CSV_TYPES.items()):
        mr = ET.SubElement(mrs, "metadata-record", {"class": "column"})
        for tag, val in [("remote-name", f), ("remote-type", REMOTE_TYPE[t]), ("local-name", f"[{f}]"),
                         ("parent-name", f"[{CSV_NAME}]"), ("remote-alias", f), ("ordinal", str(i)),
                         ("local-type", t), ("aggregation", DEFAULT_AGG[t])]:
            ET.SubElement(mr, tag).text = val
        if t == "string":
            ET.SubElement(mr, "scale").text = "1"
            ET.SubElement(mr, "width").text = "1073741823"
        ET.SubElement(mr, "contains-null").text = "true"
        if t == "string":
            ET.SubElement(mr, "collation", {"flag": "0", "name": "LEN_RUS"})
    ET.SubElement(ds, "aliases", {"enabled": "yes"})
    mn_col = ET.SubElement(ds, "column", {"datatype": "string", "name": "[:Measure Names]", "role": "dimension",
                                          "type": "nominal"})
    mn_aliases = ET.SubElement(mn_col, "aliases")
    for ci, label in KPI_LABELS:
        ET.SubElement(mn_aliases, "alias", {"key": f'"{ref(ci)}"', "value": label})
    for f in CSV_TYPES:
        if f in ("TrackingNumber", "Ward"):
            column_el(ds, f)
    for c in CALCS:
        column_el(ds, c[0])
    ET.SubElement(ds, "layout", {"dim-ordering": "alphabetic", "dim-percentage": "0.5",
                                 "measure-ordering": "alphabetic", "measure-percentage": "0.4",
                                 "show-structure": "true"})
    sv = ET.SubElement(ds, "semantic-values")
    ET.SubElement(sv, "semantic-value", {"key": "[Country].[Name]", "value": '"United States"'})

    # ------------------------------------------------------------ actions
    # Clicking a permit category filters the rest of the main dashboard
    acts = ET.SubElement(wb, "actions")
    act = ET.SubElement(acts, "action", {"caption": "Filter by Permit Category",
                                         "name": "[Action1_FY26CATEGORYFILTER]"})
    ET.SubElement(act, "activation", {"auto-clear": "true", "type": "on-select"})
    ET.SubElement(act, "source", {"dashboard": "FY26 Permit Approval Times", "type": "sheet",
                                  "worksheet": "By Permit Category"})
    cmd = ET.SubElement(act, "command", {"command": "tsc:tsl-filter"})
    ET.SubElement(cmd, "param", {"name": "exclude", "value": "By Permit Category"})
    ET.SubElement(cmd, "param", {"name": "special-fields", "value": "all"})
    ET.SubElement(cmd, "param", {"name": "target", "value": "FY26 Permit Approval Times"})

    # ------------------------------------------------------------ worksheets
    wss = ET.SubElement(wb, "worksheets")
    AVG, MED, ISS, N = usr("Calc_AvgApprove"), usr("Calc_MedApprove"), usr("Calc_AvgIssue"), usr("Calc_Permits")
    PCT, NS, DIFF, QA = usr("Calc_Pct10"), usr("Calc_PermitsScope"), usr("Calc_Diff"), usr("Calc_SumQA")
    SPEED = usr("Calc_Speed", "nk")
    bar_label = [(field_token(AVG), {"bold": "true"}), ("  (n=", None), (field_token(N), None), (")", None)]
    std_tips = [("text", AVG), ("text", N), ("tooltip", MED), ("tooltip", ISS), ("tooltip", DIFF)]
    overall_line = (AVG, agg("avg", "Calc_Overall", "Avg"), "Overall avg: <Value>")

    sheets = []

    def add(name, *a, **k):
        """Build a worksheet and record its name for the window list."""
        worksheet(wss, name, *a, **k)
        sheets.append(name)

    add("KPI - Overall", "Overall FY26 performance", [], [], "Text", [],
        show_labels=False, measure_names=KPI_MEASURES)

    add("Distribution", "How long approvals take: permits by approval-time band",
        [usr("Calc_Permits")], [dim("Calc_Band")], "Bar", [("text", N)],
        sort=(dim("Calc_Band"), agg("min", "Calc_BDApprove", "Min"), "ASC"))

    add("By Permit Category", "Average business days to approve, by permit category",
        [dim("PermitCategory")], [AVG], "Bar", std_tips + [("color", dim("WorkTypeFamily"))],
        sort=(dim("PermitCategory"), AVG, "DESC"), label_runs=bar_label, refline=overall_line)

    add("By Applicant Type", "Average business days to approve, by applicant type",
        [dim("ApplicantType")], [AVG], "Bar", std_tips + [("color", SPEED)],
        sort=(dim("ApplicantType"), AVG, "DESC"), label_runs=bar_label, refline=overall_line)

    add("Resubmission Impact", "Resubmission requested vs. not",
        [dim("ResubmissionRequested")], [AVG], "Bar", std_tips + [("color", dim("ResubmissionRequested"))],
        sort=(dim("ResubmissionRequested"), AVG, "ASC"), label_runs=bar_label, refline=overall_line)

    add("Work Location Size", "By number of blocks on the permit",
        [dim("LocationBucket")], [AVG], "Bar", std_tips,
        sort=(dim("LocationBucket"), agg("min", "NumBlockLocations", "Min"), "ASC"), label_runs=bar_label,
        refline=overall_line)

    add("Applicant x Resubmission", "Avg business days: applicant type x resubmission (gap holds in every row)",
        [dim("ApplicantType")], [dim("ResubmissionRequested")], "Square",
        [("color", AVG), ("text", AVG), ("text", N)],
        label_runs=[(field_token(AVG), {"bold": "true", "fontsize": "11"}), (NL, None),
                    ("n=", {"fontsize": "8"}), (field_token(N), {"fontsize": "8"})])

    add("Approval vs Issuance", "Business days to approve (DDOT) vs. to issue (incl. applicant payment)",
        [dim("PermitCategory")], [AVG, ISS], "Bar", [("tooltip", N)],
        sort=(dim("PermitCategory"), AVG, "DESC"))

    add("By Ward", "Average business days to approve, by ward (little variation)",
        [AVG], [dim("Ward")], "Bar", std_tips, label_runs=[(field_token(AVG), None)])

    add("Monthly Trend (censored)", "By application month",
        [AVG], [("tmn", "ApplicationDate", "qk", "Month-Trunc", "quantitative")], "Line",
        [("text", AVG), ("tooltip", N)], label_runs=[(field_token(AVG), None)],
        caption_runs=[(NL, None), ("CAUTION: late-FY months only include permits issued by 9/30/2026, "
                                   "so they are biased toward fast approvals.",
                                   {"fontsize": "9", "fontcolor": "#c00000"})])

    # ------------------------------------------------------------ dashboards
    dbs = ET.SubElement(wb, "dashboards")
    navy, sec_bg = "#1f3864", "#dce6f2"
    h1 = {"bold": "true", "fontsize": "20", "fontcolor": navy}
    h2 = {"bold": "true", "fontsize": "12", "fontcolor": navy}
    body = {"fontsize": "10", "fontcolor": "#404040"}
    small = {"fontsize": "9", "fontcolor": "#595959"}

    def dashboard(name, build_fn):
        """Append a fixed 1400x1000 dashboard whose zones are laid out by build_fn(Zones, root zone)."""
        d = ET.SubElement(dbs, "dashboard", {"name": name})
        ET.SubElement(d, "style")
        ET.SubElement(d, "size", {"maxheight": "1000", "maxwidth": "1400", "minheight": "1000", "minwidth": "1400",
                                  "sizing-mode": "fixed"})
        zs = ET.SubElement(d, "zones")
        Z = Zones()
        root = Z.zone(zs, 0, 0, 100000, 100000, **{"type-v2": "layout-basic"})
        build_fn(Z, root)

    def main_dash(Z, root):
        """Lay out the main dashboard: KPIs, distribution, category, breakdowns, takeaways, and next steps."""
        v = Z.zone(root, 0, 0, 100000, 100000, param="vert", **{"type-v2": "layout-flow"})
        y = 0
        Z.text(v, 0, y, 100000, 5000, [("FY2026 Public Space Construction Permits: Business Days to Approve", h1)])
        y += 5000
        Z.text(v, 0, y, 100000, 5000, [(
            "New permits applied for on or after Oct 1, 2025 and issued in FY26 (Oct 1, 2025 - Sep 30, 2026). "
            "Business days count from application to DDOT's final approval and exclude weekends and DC holidays. "
            "Source: DDOT TOPS, deduplicated to one row per permit. "
            "Click a permit category to filter the whole dashboard; click again to clear.", body)])
        y += 5000
        row = Z.zone(v, 0, y, 100000, 40000, param="horz", **{"type-v2": "layout-flow"})
        left = Z.zone(row, 0, y, 32000, 40000, param="vert", **{"type-v2": "layout-flow"})
        Z.text(left, 0, y, 32000, 4000, [("1 | Overall performance", h2)], bg=sec_bg)
        Z.zone(left, 0, y + 4000, 32000, 21000, name="KPI - Overall", **{"show-title": "false"})
        Z.zone(left, 0, y + 25000, 32000, 15000, name="Distribution")
        right = Z.zone(row, 32000, y, 68000, 40000, param="vert", **{"type-v2": "layout-flow"})
        Z.text(right, 32000, y, 68000, 4000, [("2 | By permit type category", h2), ("   Click a bar to filter the dashboard; line = overall average; "
                                                "Excavation is split by utility because it is 90% of permits", small)], bg=sec_bg)
        Z.zone(right, 32000, y + 4000, 68000, 36000, name="By Permit Category")
        y += 40000
        Z.text(v, 0, y, 100000, 4000, [("3 | Where approval times differ", h2),
                                       ("   Resubmission and project size separate fast from slow; geography does not (see Data Segmentation tab)", small)],
               bg=sec_bg)
        y += 4000
        row = Z.zone(v, 0, y, 100000, 31000, param="horz", **{"type-v2": "layout-flow"})
        Z.zone(row, 0, y, 34000, 31000, name="By Applicant Type")
        Z.zone(row, 34000, y, 33000, 31000, name="Resubmission Impact")
        Z.zone(row, 67000, y, 33000, 31000, name="Work Location Size")
        y += 31000
        row = Z.zone(v, 0, y, 100000, 15000, param="horz", **{"type-v2": "layout-flow"})
        Z.text(row, 0, y, 62000, 15000, [
            ("Key takeaways", h2), (NL, None),
            ("- 22.2 avg / 13 median business days. The average blends a same-day group (22%) with a 60+ day tail (9%).", body), (NL, None),
            ("- Widest gap is resubmission: 12.4 vs 48.3 days. 27% of permits account for 59% of approval days.", body), (NL, None),
            ("- Project size: 1 block 13.5 days vs 6-20 blocks 51.7. DC Water single-block permits take 7 days, multi-block 41-52.", body), (NL, None),
            ("- Category: Sewer/Storm 0.9 and Gas 8.0, up to Water 35.7 and Multiple Work Types 51.0. Water is 32% of permits and 51% of approval days.", body), (NL, None),
            ("- Applicant: Washington Gas 8.9, DC Water 31.2, Private 44.1. Private applicants are asked to resubmit 68% of the time.", body),
        ], bg="#f2f2f2")
        Z.text(row, 62000, y, 38000, 15000, [
            ("Next steps", h2), (NL, None),
            ("1. Analyze reasons for Revise & Resubmit requests by category.", body), (NL, None),
            ("2. Review DC Water multi-block lateral work as a program.", body), (NL, None),
            ("3. Split time into queue, review, and applicant-payment stages.", body), (NL, None),
            ("4. Use cohort-based trends (the monthly view is cut off at year end).", body), (NL, None),
            ("Holidays excluded: 10/13, 11/11, 11/27, 12/25, 1/1, 1/19, 2/16, 4/16, 5/25, 6/19, 7/3, 9/7", small), (NL, None),
            ("5 of 2,992 in-scope permits have no approval date and are left out of the business-day averages (n = 2,987).", small),
        ], bg="#f2f2f2")

    def deep_dash(Z, root):
        """Lay out the Data Segmentation dashboard as a 2x2 grid of cross-check sheets above a key takeaways box."""
        v = Z.zone(root, 0, 0, 100000, 100000, param="vert", **{"type-v2": "layout-flow"})
        Z.text(v, 0, 0, 100000, 8000, [("Data segmentation: what separates fast and slow approvals", h1), (NL, None),
                                       ("Cross-checks behind the main dashboard: is the gap real within each group, and where does time go after approval?", body)])
        row = Z.zone(v, 0, 8000, 100000, 36000, param="horz", **{"type-v2": "layout-flow"})
        Z.zone(row, 0, 8000, 50000, 36000, name="Applicant x Resubmission")
        Z.zone(row, 50000, 8000, 50000, 36000, name="Approval vs Issuance")
        row = Z.zone(v, 0, 44000, 100000, 36000, param="horz", **{"type-v2": "layout-flow"})
        Z.zone(row, 0, 44000, 50000, 36000, name="By Ward")
        Z.zone(row, 50000, 44000, 50000, 36000, name="Monthly Trend (censored)")
        Z.text(v, 0, 80000, 100000, 20000, [
            ("Key takeaways", h2), (NL, None),
            ("- Resubmission gap holds for every applicant type: Washington Gas 5.5 vs 33.6 days, DC Water 19.6 vs 54.9, Private 20.3 vs 55.2. It is not an applicant-mix effect.", body), (NL, None),
            ("- Most permits issue 3-5 business days after approval. Excavation - Gas is the exception: 8.0 days to approve but 55.3 to issue, and it holds 87% of all post-approval days.", body), (NL, None),
            ("- The gas issuance wait is skewed (median 6 days, but 36% wait 20+), so it points to a payment or pickup step on a subset of permits, not to DDOT review.", body), (NL, None),
            ("- Geography explains little: Wards 1-8 average 18.2 to 27.2 days with medians of 9 to 17. Only the 18 multi-ward permits stand out (36.8).", body), (NL, None),
            ("- The monthly drop is not an improvement: Oct-May applications average 37.6 days vs 12.4 for Jun-Sep, because slow late-year permits were not yet issued by 9/30.", body), (NL, None),
            ("- Where to act: Revise & Resubmit requests and the gas approval-to-issuance gap, not ward-level or seasonal factors.", body),
        ], bg="#f2f2f2")

    D1, D2 = "FY26 Permit Approval Times", "Data Segmentation"
    dashboard(D1, main_dash)
    dashboard(D2, deep_dash)

    # ------------------------------------------------------------ windows
    wins = ET.SubElement(wb, "windows", {"source-height": "30"})
    for s in sheets:
        w = ET.SubElement(wins, "window", {"class": "worksheet", "name": s})
        cards = ET.SubElement(w, "cards")
        left = ET.SubElement(cards, "edge", {"name": "left"})
        strip = ET.SubElement(left, "strip", {"size": "160"})
        for c in ("pages", "filters", "marks"):
            ET.SubElement(strip, "card", {"type": c})
        top = ET.SubElement(cards, "edge", {"name": "top"})
        for c, size in (("columns", "2147483647"), ("rows", "2147483647"), ("title", "2147483647")):
            ET.SubElement(ET.SubElement(top, "strip", {"size": size}), "card", {"type": c})
    for d, names in ((D1, ["KPI - Overall", "Distribution", "By Permit Category", "By Applicant Type",
                           "Resubmission Impact", "Work Location Size"]),
                     (D2, ["Applicant x Resubmission", "Approval vs Issuance", "By Ward", "Monthly Trend (censored)"])):
        w = ET.SubElement(wins, "window", {"class": "dashboard", "maximized": "true" if d == D1 else "false", "name": d})
        vps = ET.SubElement(w, "viewpoints")
        for n in names:
            ET.SubElement(vps, "viewpoint", {"name": n})
        ET.SubElement(w, "active", {"id": "-1"})

    # ------------------------------------------------------------ write
    ET.indent(wb, space="  ")
    xml = b"<?xml version='1.0' encoding='utf-8' ?>\n\n" + ET.tostring(wb, encoding="utf-8")
    base = "FY26_Public_Space_Permit_Approvals"
    twb_path = os.path.join(project, f"{base}.twb")
    with open(twb_path, "wb") as f:
        f.write(xml)
    twbx_path = os.path.join(project, f"{base}.twbx")
    with zipfile.ZipFile(twbx_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{base}.twb", xml)
        z.write(os.path.join(project, "data", CSV_NAME), f"{PKG_DIR}/{CSV_NAME}")
        z.write(os.path.join(project, "data", "dc_holidays.csv"), f"{PKG_DIR}/dc_holidays.csv")
    print("wrote", twbx_path, "with", len(sheets), "worksheets and 2 dashboards")


if __name__ == "__main__":
    build()
