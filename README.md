# FY2026 Public Space Construction Permit Approval Times — Tableau Project

This Tableau analysis measures the **average business days to approve new Public Space Construction Permits issued in FY2026** (Oct 1, 2025 – Sep 30, 2026). It breaks the results down by segment to show **where approval times are meaningfully different**, as requested by the Associate Director of the Public Space Division.

> **Headline:** new FY26 permits took **22.2 business days** on average to approve (median **13**, n = **2,987**). The widest gaps are by **resubmission** (12.4 vs. 48.3 days) and **project size** (single block 13.5 vs. 6–20 blocks 51.7). Resubmitted permits are 27% of permits but use **59% of all approval days**.
>
> The full findings are in **[REPORT_SUMMARY.md](REPORT_SUMMARY.md)**.

---

## 1. Contents

```
tableau-workbook/
├── README.md                          ← you are here: overview, method, reproduction
├── REPORT_SUMMARY.md                  ← findings report (insights, methodology, limitations)
├── Tableau_Build_Guide.md             ← step-by-step build instructions for Tableau Desktop
├── FY26_Public_Space_Permit_Approvals.twbx   ← packaged Tableau workbook (10 worksheets, 2 dashboards)
├── scripts/
│   ├── 01_pull_permits.py             ← pages through the ArcGIS REST feed
│   └── 02_prepare_permits.py          ← dedupe, time zones, categories, business days
└── data/
    ├── permits_by_tracking_number.csv ← Tableau data source (one row per permit)
    ├── dc_holidays.csv                ← DC holidays excluded from business days
    └── raw/permits_raw.json           ← raw REST pull (not included in the submission zip)
```

## 2. Deliverables mapped to the request

| Requirement (from the assignment) | Where it is delivered |
|---|---|
| (1) Worksheet: average business days to approve | **KPI: Overall Avg Business Days**, plus an optional distribution histogram |
| (2) Worksheet: average by permit type category | **Avg Business Days by Permit Category** (14 categories, with an overall-average reference line) |
| (3) Worksheet: another helpful segment | **Avg Business Days by Applicant Type**, plus **Resubmission Impact**, **Work Location Size**, **Approval vs. Issuance Gap** and **Ward** |
| (4) Dashboard with layout, title, section titles and guiding text | **FY26 Permit Approval Times** dashboard: title, subtitle with definitions, three numbered sections, a key-takeaways box, a next-steps box with the holiday list, overall-average reference lines, and click-to-filter by permit category |
| Filter: application date on or after 10/1/2025 | `In Scope (FY26 New Issued)` calculation, applied as a filter on every sheet and built into the business-day measures |
| Filter: only *new* permits *issued* in FY26 | `RenewalDescription = "New"` and `IssueDate` from 10/1/2025 to 9/30/2026 |
| Business days exclude weekends and DC holidays | `Business Days to Approve` calculation, checked against an independent Python count |
| Packaged and zipped | `.twbx` in `FirstName_MiddleInitial_LastName_Tableau.zip` |

## 3. Data source

- **Feed:** DDOT TOPS, *Public Space Construction Permits – Status* (MapServer layer 23)
  `https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23`
- **Spot-check tool:** https://tops.ddot.dc.gov/DDOTPERMITSYSTEM/DDOTPERMITonline/landing.aspx
- **Pulled:** 2026-10-13. 50,649 rows had an application date on or after 10/1/2025, covering 9,747 unique permits.

## 4. Approach summary, and why

| Step | What was done | Why |
|---|---|---|
| **Acquire** | A scripted REST pull, paged 2,000 records at a time with retries, filtered on the server to application dates on or after 10/1/2025 | Tableau has no native ArcGIS REST connector. A script can be re-run and audited, and it keeps every field. |
| **Understand the grain** | Profiled the data and found **one row per work block**, not one per permit. A single permit has up to 176 rows. | Averaging raw rows would weight large projects far more heavily and distort every result. |
| **Deduplicate** | One row per `TrackingNumber`, with the block count kept as `NumBlockLocations` | Gives correct permit-level averages and turns project size into a segment. |
| **Identify "new" permits** | Used `RenewalDescription`, not `PermitTypeDescription` | `PermitTypeDescription` says "New" even for renewals. Renewal permit numbers end in `-R#`. |
| **Identify "issued in FY26"** | Filtered on `IssueDate`, not `FiscalYear` | `FiscalYear` follows the application date. |
| **Time zones** | Converted UTC epoch values to America/New_York dates | Avoids moving evening submissions to the wrong day. |
| **Choose the metric** | Application → Last Approval (primary). Application → Issue (secondary). | Approval reflects DDOT's work. Issuance adds the applicant's fee-payment time. |
| **Business days** | Weekdays after the application date up to and including approval, minus 13 DC holidays. Same-day approval = 0. | Matches `NETWORKDAYS − 1`. Built as both a Tableau formula and a Python count, with **0 mismatches across 8,479 permits**. |
| **Categorize** | Parsed `TypeDetailNames` ("Family; Detail"). Excavation (90% of permits) split by utility. Permits spanning several families are labeled "Multiple Work Types". | A family-only view would be one large bar. The utility split shows a 0.9 to 36 day range within Excavation. |
| **Segment** | Tested 9 candidate segments. Kept those with large gaps, enough permits, a gap that holds in cross-tabs, and a clear next step. | The brief asks for segmentation to guide deeper analysis, not statistical modeling. |

See [REPORT_SUMMARY.md §3](REPORT_SUMMARY.md#3-approach-and-methodology) for the full methodology and the evidence behind each decision.

## 5. Key insights (summary)

| # | Insight | Numbers |
|---|---|---|
| 1 | The overall figure combines a fast group and a slow group | 22% approved the same day. 9% take more than 60 days. Mean 22.2, median 13. |
| 2 | **Resubmission shows the widest gap** | 12.4 vs. 48.3 days. 27% of permits account for 59% of approval days. The gap holds within every applicant type. |
| 3 | **Project size shows the second widest gap** | 1 block: 13.5 days. 6–20 blocks: 51.7. DC Water single-block permits take 7.1 days and its multi-block permits 41–52. |
| 4 | Permit category ranges widely | Sewer/Storm 0.9 and Gas 8.0, up to Water 35.7 and Multiple Work Types 51.0. Water is 32% of permits and 51% of approval days. |
| 5 | Applicant gaps overlap with what each applicant files | Washington Gas 8.9, DC Water 31.2, Private 44.1. Private applicants are asked to resubmit 68% of the time, compared with 12% for Washington Gas. |
| 6 | Public Space Committee review is a separate, slow track | 86.4 vs. 21.3 days (n = 41) |
| 7 | Time after approval is a separate issue | Issuance adds about 22 business days on average, driven by fee payment |
| 8 | Ward shows little difference | Wards range from 18 to 27 days |
| 9 | The monthly trend is affected by the year-end cut-off | The apparent improvement in late-FY months is an artifact. Use cohort tracking. |

## 6. How to reproduce

**Requirements:** Python 3.9 or later (standard library only) for the data steps, and Tableau Desktop.

```bash
# 1. Pull raw data (~2 minutes)
python3 scripts/01_pull_permits.py data/raw/permits_raw.json

# 2. Build the Tableau-ready files
python3 scripts/02_prepare_permits.py data/raw/permits_raw.json data
#    -> "50649 raw rows -> 9747 permits"
```

3. Build the workbook in Tableau Desktop by following **[Tableau_Build_Guide.md](Tableau_Build_Guide.md)**. It covers connecting the data, 20 calculated fields, the scope filter, 10 worksheets, 2 dashboards, the filter action and packaging, with expected values to check at every step.
4. Validate the workbook. The KPI sheet shows all three checks:
   - Permits in scope = **2,992**
   - QA mismatches = **0**
   - Average business days to approve = **22.2** (n = **2,987** with an approval date)
5. Save as a packaged workbook (`.twbx`) and zip it with the required name, `Fulton_Q_Shannon_Tableau.zip`. The guide's §7.3 lists the files.

> Note: the feed is live. Re-pulling the data later will change the counts slightly as permits are updated.

## 7. Data dictionary (`permits_by_tracking_number.csv`)

The feed has no official data dictionary. These fields are derived or renamed by `02_prepare_permits.py`.

| Field | Description |
|---|---|
| `TrackingNumber` | Unique permit application ID (the unit of analysis) |
| `PermitNumber` | Issued permit number (`PA######`; renewals end in `-R#`) |
| `Status` | Current status (Issued, Permit Expired, …) |
| `NewOrRenewal` | From `RenewalDescription`: New / Renewal |
| `ApplicationDate`, `ApprovalDate`, `IssueDate` | Eastern-time calendar dates. ApprovalDate = `LastApprovalDate`. |
| `IssuedInFY26` | 1 if IssueDate falls between 10/1/2025 and 9/30/2026 |
| `BusinessDaysToApprove_QA`, `BusinessDaysToIssue_QA` | Business days computed in Python, used to check the Tableau calculation |
| `CalendarDaysToApprove` | Calendar days from application to approval |
| `WorkTypeFamily` | Excavation / Paving / Fixture / Over Head Work / Landscaping / Projections / Multiple Work Types |
| `PermitCategory` | WorkTypeFamily, with Excavation split by utility |
| `TypeDetailNames`, `NumWorkTypes` | Raw work-type detail and the number of detail items |
| `ApplicantType` | Washington Gas / DC Water / Pepco / Telecom / Government Agency / Private-Other, matched by keyword from the permittee and applicant company |
| `ResubmissionRequested` | Yes if `LastResubmissionRequestDate` is populated |
| `PSCReview` | Yes if `PCReviewStatus` is populated (Public Space Committee) |
| `NumBlockLocations`, `LocationBucket` | Number of block rows in the raw feed, and the bucket it falls in (1 / 2–5 / 6–20 / 21+) |
| `Ward`, `Quadrant`, `Latitude`, `Longitude`, `WorkLocation` | Location of the first block. `Ward` is "Multiple Wards" when blocks span more than one ward. |
| `TotalFee`, `PermitteeName` | As provided in the feed |

## 8. Limitations

- Only permits **issued** in FY26 are included. Permits still pending are left out, which pulls the averages down, especially for late-year applications.
- `LastApprovalDate` is overwritten when a permit is reapproved, so separate review cycles can't be measured.
- Applicant type and permit category come from keyword rules. They are documented in the script and can be adjusted.
- The results are descriptive segments, not causal estimates (per the brief).
