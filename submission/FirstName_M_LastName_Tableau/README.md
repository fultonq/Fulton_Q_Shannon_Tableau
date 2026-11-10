# DDOT FY26 Public Space Construction Permits: Average Business Days to Approve

This is a Tableau analysis for the Associate Director of the Public Space Division. It covers **average business days to approve Public Space Construction Permits in FY26**, segmented to show where approval times differ meaningfully. It was prepared for the CS12 Data Scientist Tableau test (Analytics, Assets, and Performance Branch).

## At a glance

| Measure | FY26 value |
|---|---|
| Permits in scope | **11,206** |
| Average business days to approve | **43.8** (median 39) |
| Approved the same day | 3.3% |
| Over 60 business days | 23.6% |
| Average business days, application to issuance | 52.3 |
| Lead Free DC program vs. all other permits | 48.4 vs. 19.5 |

## Scope and definitions

**Permits included:**
- **Source:** DC GIS REST feed, [`DCGIS_APPS/DDOT_TOPS/MapServer/23`](https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23) (*DDOT – Public Space Construction Permits – Status*).
- **Filters:**
  - Application date on or after **Oct 1, 2025**.
  - **New** permits only (`RenewalDescription = "New"`; renewals are excluded).
  - **Issued in FY26** (`IssueDate` from Oct 1, 2025 to Sep 30, 2026).

**Business days:**
- Counted from the application date to the final approval date (`LastApprovalDate`).
- Weekends and **District of Columbia holidays** are excluded, including DC Emancipation Day and observed dates.
- A permit approved on the day it was submitted counts as 0.

**Permit type category** (there is no data dictionary):
- Built from each permit's line items (`TypeDetailNames`).
- Permits carrying only the standard three-item DC Water Lead Free DC set are classed as *Lead Service Line Replacement*.
- Other excavation permits are grouped as gas, water/sewer, electric/telecom, mega project or other.
- Non-excavation permits use their TOPS work type: Fixture, Paving, Overhead Work, Landscaping or Projections.

## Project structure

```
tableau-cs12-Data-scientist/
├── README.md                     This file
├── APPROACH.md                   Method, filters, findings, next steps, limits
├── MANUAL_BUILD_GUIDE.md         Step-by-step guide to building the workbook by hand in Tableau Desktop
├── Tableau Test - CS12 Data Scientist.pdf   The original request
├── scripts/
│   ├── pull_permits.py           Downloads permits from the REST feed (paged) -> data/raw_permits.csv
│   ├── prepare_permits.py        Filters, computes business days, adds segments -> data/fy26_new_issued_permits.csv
│   ├── segment_summary.py        Segment vs. average comparison -> data/segment_comparison.csv
│   ├── build_workbook.py         Generates the .twb XML and packages the .twbx
│   ├── explore.py, explore2.py   Data profiling used to design the categories
├── data/
│   ├── raw_permits.csv           All permits applied for since 2025-10-01 (50,964 rows)
│   ├── fy26_new_issued_permits.csv  Tableau data source (11,206 rows)
│   ├── segment_comparison.csv    Purpose-built segment comparison (second Tableau data source)
│   └── dc_holidays.csv           Holidays excluded from business days
├── workbook/
│   ├── DDOT_FY26_Permit_Approval_Times.twbx   Packaged workbook (data embedded)
│   ├── DDOT_FY26_Permit_Approval_Times.twb    Unpackaged workbook
│   └── Data/permits/…            CSV referenced by the .twb
└── submission/
    ├── FirstName_M_LastName_Tableau/          Submission contents
    └── FirstName_M_LastName_Tableau.zip       Zip to submit (rename with your name)
```

## Workbook contents

| Sheet | Purpose |
|---|---|
| 1. Overall Avg Business Days | Headline numbers: average, median, permit count, % same day, % over 60, days to issuance |
| 2. Avg Days by Permit Type | Average by permit type category (required) |
| 3. Lead Free DC vs All Other | The segment that splits the data most |
| 4. Avg Days by Applicant | Utility / applicant group |
| 5. Approval Time Distribution | Permits in each business-day band |
| 6. Trend by Application Month | Monthly trend (see the caveat below) |
| 7. Avg Days by Ward | Geography |
| 8. Approval vs Issuance by Applicant | DDOT approval stage vs. the applicant's payment and pick-up stage |
| 9. Segments vs FY26 Average | Every segment (30+ permits) whose average is 7+ business days above or below 43.8 |
| 10. Segments excl. Lead Free DC | The same test with Lead Free DC removed (average 19.5), so program mix doesn't drive the result |
| 11. Ward x Program Heatmap | Ward by program: ward gaps exist only inside Lead Free DC |
| **FY26 Permit Approval Dashboard** | Title, guidance, four titled sections (section 4: *Where approval times are meaningfully different*) and key insights |

## Rebuilding

You need Python 3.11+ on Windows.

```powershell
cd X:\tableau-cs12-Data-scientist
python -m venv .venv
.venv\Scripts\pip install pandas requests holidays numpy

.venv\Scripts\python scripts\pull_permits.py      # ~1 min: pulls the live feed
.venv\Scripts\python scripts\prepare_permits.py   # filters and enriches; prints segment summaries
.venv\Scripts\python scripts\segment_summary.py   # segment vs. average comparison
.venv\Scripts\python scripts\build_workbook.py    # writes workbook\*.twb and *.twbx
```

The feed is live, so a later pull may change the counts slightly.

To build the workbook in Tableau Desktop instead, follow **MANUAL_BUILD_GUIDE.md**. Its section 10 lists the expected numbers to check against.

## Key findings

1. **One program drives the average.**
   - DC Water's Lead Free DC lead service line permits are 84% of FY26 new issued permits and average **48.4** business days.
   - Everything else averages **19.5**.
2. **Permit type matters.**

   | Permit type | Avg business days |
   |---|---|
   | Gas | 10.0 |
   | Water/sewer | 19.1 |
   | Electric/telecom | 25.2 |
   | Paving | 35.5 |
   | Fixtures | 50.0 |
   | Other excavation | 57.8 |

3. **Approval vs. issuance.** Washington Gas is approved in 11.5 days but waits about 45 more before issuance. Its delay is on the applicant's side (payment and pick-up), not in DDOT's review.
4. **Meaningfully different segments** (7+ business days from the average, 30+ permits):
   - Slower: Public Space Committee review (72.0), Q1–Q2 applications (69–71), Ward 3 (60.1), other excavation (57.8).
   - Faster: DC Water non-lead work (5.2), gas (10.0), single-line-item permits (14.2), Ward 8 (28.4).
   - With Lead Free DC excluded, complexity drives the time: permits with 4+ line items, committee review, fixtures and private applicants take 30–50 days longer than the 19.5-day average.
5. **Ward is a Lead Free DC effect.** Within the program, Ward 3 averages 68.9 days and Ward 8 30.2. For all other permits, every ward is 15–24 days.
6. **Timing and place.**
   - Applications from Oct 2025 to Mar 2026 averaged 65–110 days.
   - Ward 3 is slowest (60.1) and Ward 8 fastest (28.4).
   - Permits reviewed by the Public Space Committee average 72.0 days.

See **APPROACH.md** for the full findings and suggested next steps.

## Known limits

- **Censoring in the monthly trend:** only permits issued by Sep 30, 2026 are included, so recent application months look faster than they will turn out to be.
- **Missing approval dates:** 13 issued permits have none; they are counted in totals but left out of the approval averages.
- **Resubmissions:** time is measured from the original application, so applicant revision time is included.
- **Generated workbook:** the workbook XML is generated by script. It has been opened and checked in Tableau Desktop 2026.3.

## Submission

Rename `submission\FirstName_M_LastName_Tableau.zip` to `FirstName_MiddleInitial_LastName_Tableau.zip` with your real name. It contains:
- the packaged workbook
- README.md
- APPROACH.md
- MANUAL_BUILD_GUIDE.md
- the scripts
- the cleaned data and holiday list

AI tools were used to help build this, as the request allows.
