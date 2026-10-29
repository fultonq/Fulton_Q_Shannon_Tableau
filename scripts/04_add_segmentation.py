"""Add the segmentation views to a workbook saved from Tableau Desktop, keeping its existing layout.

Usage: python3 04_add_segmentation.py <saved .twbx> <output .twbx>

03_build_twbx.py regenerates every dashboard from scratch, which would discard layout changes made by
hand in Tableau Desktop. This script instead edits the saved .twb as text and leaves every existing
byte in place. It only adds:
  - calculated field  Project Size (1 vs 2+ blocks)   [Calc_SizeBand]
  - worksheet         Blocks x Resubmission           heat map, cloned from Applicant x Resubmission
  - worksheet         Applicant x Project Size        heat map, cloned from Applicant x Resubmission
  - worksheet         PSC Review Impact               bars, cloned from Resubmission Impact
  - dashboard         Where Times Differ              the three sheets plus a takeaways text box
The figures in the takeaways text are typed in, like the other dashboards' text; they match the
FY26 data pulled 2026-10-13 and must be updated by hand after a new pull.
"""
import re, sys, uuid, zipfile

DSQ = "[federated.fy26permits0001]"
NL = "Æ&#10;"  # Tableau's paragraph break inside formatted text
NEW_SHEETS = ["Blocks x Resubmission", "Applicant x Project Size", "PSC Review Impact"]
DASH = "Where Times Differ"

SIZE_CALC = ("<column caption='Project Size (1 vs 2+ blocks)' datatype='string' name='[Calc_SizeBand]' "
             "role='dimension' type='nominal'>\n{i}  <calculation class='tableau' formula='IF [NumBlockLocations] = 1 "
             "THEN &quot;1 block&quot; ELSE &quot;2+ blocks&quot; END' />\n{i}</column>")
PSC_COLORS = """          <encoding attr='color' field='[none:PSCReview:nk]' type='palette'>
            <map to='#4e79a7'>
              <bucket>&quot;No&quot;</bucket>
            </map>
            <map to='#f28e2b'>
              <bucket>&quot;Yes&quot;</bucket>
            </map>
          </encoding>
"""

# Helper functions for manipulating Tableau XML elements
def new_uuid():
    """Return a fresh {UPPERCASE-UUID} for a simple-id element."""
    return "{" + str(uuid.uuid4()).upper() + "}"

# Extract a specific XML block by tag and name
def block(xml, tag, name):
    """Return the full <tag name='name'>...</tag> element text from xml; fails if it isn't there exactly once."""
    found = re.findall(rf"    <{tag} (?:class='[a-z]+' )?(?:maximized='true' )?name='{re.escape(name)}'>.*?\n    </{tag}>", xml, re.S)
    assert len(found) == 1, (tag, name, len(found))
    return found[0]

# Replace exactly one occurrence of a string in the XML
def replace_once(xml, old, new):
    """Replace exactly one occurrence of old, so a changed source file fails loudly instead of half-patching."""
    assert xml.count(old) == 1, (old[:80], xml.count(old))
    return xml.replace(old, new)

# Retitle a worksheet and update its title and simple-id
def retitle(sheet, name, title):
    """Rename a cloned worksheet, set its title text and give it a new simple-id."""
    sheet = re.sub(r"<worksheet name='[^']+'>", f"<worksheet name='{name}'>", sheet, count=1)
    sheet = re.sub(r"(<title>\s*<formatted-text>\s*<run bold='true' fontsize='12'>)[^<]*(</run>)",
                   rf"\g<1>{title}\g<2>", sheet, count=1)
    return re.sub(r"<simple-id uuid='[^']+' />", f"<simple-id uuid='{new_uuid()}' />", sheet)

# Update a worksheet to depend on the project size calculation instead of a string field
def size_dependency(sheet, field):
    """Swap the dependency on string field for Calc_SizeBand and the block count it reads."""
    i = " " * 12
    return replace_once(sheet, f"\n{i}<column datatype='string' name='[{field}]' role='dimension' type='nominal' />",
                        f"\n{i}" + SIZE_CALC.format(i=i) +
                        f"\n{i}<column datatype='integer' name='[NumBlockLocations]' role='measure' type='quantitative' />")

# Extract the relevant worksheets from the Tableau XML
def sheets(xml):
    """Build the three new worksheets from the saved Applicant x Resubmission and Resubmission Impact sheets."""
    heat = block(xml, "worksheet", "Applicant x Resubmission")
    bars = block(xml, "worksheet", "Resubmission Impact")

    blocks = retitle(heat, "Blocks x Resubmission",
                     "Avg business days: project size x resubmission (both gaps hold)")
    blocks = size_dependency(blocks, "ApplicantType").replace("ApplicantType", "Calc_SizeBand")

    appl = retitle(heat, "Applicant x Project Size",
                   "Avg business days: applicant type x project size (DC Water is slow only on multi-block work)")
    appl = size_dependency(appl, "ResubmissionRequested").replace("ResubmissionRequested", "Calc_SizeBand")

    psc = retitle(bars, "PSC Review Impact", "Public Space Committee review vs. not")
    psc = psc.replace("ResubmissionRequested", "PSCReview")
    return blocks, appl, psc

# Build the dashboard XML for the "Where Times Differ" view
def dashboard():
    """Return the Where Times Differ dashboard: title, two heat maps, the PSC bars and a takeaways box."""
    # Helper function to wrap text in a run element with optional attributes
    def run(text, **a):
        attrs = "".join(f" {k}='{v}'" for k, v in a.items())
        return f"<run{attrs}>{text}</run>"
    title = (run("Where approval times are meaningfully different", bold="true", fontcolor="#1f3864", fontsize="20") +
             run(NL) + run("Segments that each explain a large share of the variation, tested against each other. "
                           "FY26 new permits issued; business days from application to DDOT's last approval.",
                           fontcolor="#404040", fontsize="10"))
    points = [
        ("Fast lane: ", "single-block permits never sent back average 7.0 days (median 1). "
                        "They are 1,763 permits, 59% of the total."),
        ("Slow lane: ", "multi-block permits that were sent back average 58.2 days (379 permits)."),
        ("Both gaps are real: ", "resubmission adds 33 days on single-block permits and 22 on multi-block ones, "
                                 "and size adds 18 to 29 days whether or not a permit is sent back."),
        ("DC Water: ", "its single-block permits average 7.1 days, close to Washington Gas (8.4). The slowness "
                       "is its multi-block lateral work, at 48.3 days."),
        ("PSC review: ", "41 permits average 86.4 days vs. 21.3, and 71% take over 60 days. Mostly private "
                         "applicants doing multiple work types or fixtures."),
        ("Read with care: ", "groups under about 30 permits (Landscaping, Projections, Government Agency) "
                             "have wide uncertainty; the n on each bar shows the count."),
    ]
    body = run("Key takeaways", bold="true", fontcolor="#1f3864", fontsize="13") + run(NL)
    body += run(NL).join(run("• " + b, bold="true", fontsize="10") + run(t, fontsize="10") for b, t in points)

    # Helper function to create a zone element in the dashboard XML
    def zone(zid, name, x, y, w, h):
        return f"<zone h='{h}' id='{zid}' name='{name}' w='{w}' x='{x}' y='{y}' />"
    return f"""    <dashboard name='{DASH}'>
      <style />
      <size maxheight='1000' maxwidth='1400' minheight='1000' minwidth='1400' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='100000' id='2' param='vert' type-v2='layout-flow' w='100000' x='0' y='0'>
            <zone h='6500' id='3' type-v2='text' w='100000' x='0' y='0'>
              <formatted-text>
                {title}
              </formatted-text>
            </zone>
            <zone h='38000' id='4' param='horz' type-v2='layout-flow' w='100000' x='0' y='6500'>
              {zone(5, "Blocks x Resubmission", 0, 6500, 40000, 38000)}
              {zone(6, "PSC Review Impact", 40000, 6500, 60000, 38000)}
            </zone>
            <zone h='55500' id='7' param='horz' type-v2='layout-flow' w='100000' x='0' y='44500'>
              {zone(8, "Applicant x Project Size", 0, 44500, 50000, 55500)}
              <zone h='55500' id='9' type-v2='text' w='50000' x='50000' y='44500'>
                <formatted-text>
                  {body}
                </formatted-text>
              </zone>
            </zone>
          </zone>
        </zone>
      </zones>
      <simple-id uuid='{new_uuid()}' />
    </dashboard>
"""

# Generate window entries for the new sheets and the new dashboard
def windows(xml):
    """Return window entries for the new sheets (copied from Work Location Size's) and the new dashboard."""
    tmpl = block(xml, "window", "Work Location Size")
    out = ""
    for name in NEW_SHEETS:
        w = tmpl.replace("name='Work Location Size'", f"name='{name}'")
        out += re.sub(r"<simple-id uuid='[^']+' />", f"<simple-id uuid='{new_uuid()}' />", w) + "\n"
    vps = "".join(f"        <viewpoint name='{n}' />\n" for n in sorted(NEW_SHEETS))
    return out + f"""    <window class='dashboard' name='{DASH}'>
      <viewpoints>
{vps}      </viewpoints>
      <active id='-1' />
      <simple-id uuid='{new_uuid()}' />
    </window>
"""

# Patch the Tableau XML to insert the new calculations, color mappings, worksheets, dashboard, and windows
def patch(xml):
    """Insert the calc, color mapping, worksheets, dashboard and windows into the saved workbook XML."""
    assert f"name='{DASH}'" not in xml, "workbook already has the segmentation dashboard"
    i = " " * 6
    xml = replace_once(xml, f"\n{i}<column caption='Speed vs Overall'",
                       f"\n{i}" + SIZE_CALC.format(i=i) + f"\n{i}<column caption='Speed vs Overall'")
    xml = replace_once(xml, "          </encoding>\n        </style-rule>\n      </style>\n      <semantic-values>",
                       "          </encoding>\n" + PSC_COLORS + "        </style-rule>\n      </style>\n      <semantic-values>")
    new_ws, new_win = "\n".join(sheets(xml)) + "\n", windows(xml)
    xml = replace_once(xml, "  </worksheets>\n", new_ws + "  </worksheets>\n")
    xml = replace_once(xml, "  </dashboards>\n", dashboard() + "  </dashboards>\n")
    return replace_once(xml, "  </windows>\n", new_win + "  </windows>\n")

# Main entry point for the script
def main(src, dst):
    """Copy every member of src into dst, patching the one .twb inside."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        twbs = [n for n in zin.namelist() if n.endswith(".twb")]
        assert len(twbs) == 1, twbs
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == twbs[0]:
                text = data.decode("utf-8")
                crlf = "\r\n" in text  # Tableau Desktop on Windows saves with CRLF line endings
                text = patch(text.replace("\r\n", "\n"))
                data = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            zout.writestr(item, data)
    print("wrote", dst, "with", ", ".join(NEW_SHEETS), "and dashboard", DASH)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
