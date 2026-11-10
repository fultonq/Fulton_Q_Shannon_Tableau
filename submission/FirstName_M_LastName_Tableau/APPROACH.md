# FY26 Public Space Construction Permits: Average Business Days to Approve

## Deliverable
`workbook/DDOT_FY26_Permit_Approval_Times.twbx` is the packaged Tableau workbook. The data is embedded in it.

| Sheet | What it shows |
|---|---|
| 1. Overall Avg Business Days | KPIs: average and median days, permit count, % same day, % over 60 days, days to issuance |
| 2. Avg Days by Permit Type | Average business days to approve for each permit type category |
| 3. Lead Free DC vs All Other | The segment that splits the data most |
| 4. Avg Days by Applicant | Applicant / utility group |
| 5. Approval Time Distribution | Permits in each business-day band, split by Lead Free DC |
| 6. Trend by Application Month | Average by month of application |
| 7. Avg Days by Ward | Geography |
| 8. Approval vs Issuance by Applicant | Time in the approval stage vs. the approval-to-issuance stage |
| 9. Segments vs FY26 Average | Every segment (30+ permits) whose average is 7+ business days above or below 43.8 |
| 10. Segments excl. Lead Free DC | The same test with Lead Free DC removed (average 19.5), so program mix doesn't drive the result |
| 11. Ward x Program Heatmap | Ward by program: ward gaps exist only inside Lead Free DC |
| **FY26 Permit Approval Dashboard** | Title, guidance text, four titled sections (including "Where approval times are meaningfully different"), key insights |

## Data pipeline (Python)
1. `scripts/pull_permits.py` reads the DC GIS REST feed (`DDOT_TOPS/MapServer/23`).
   - It pages through all permits with `ApplicationDate >= 2025-10-01`, 2,000 at a time: 50,964 records.
   - It converts epoch-millisecond dates to Eastern time.
   - It writes `data/raw_permits.csv`.
2. `scripts/prepare_permits.py` filters the data and adds new fields. It writes `data/fy26_new_issued_permits.csv` (11,206 permits) and `data/dc_holidays.csv`.
3. `scripts/segment_summary.py` writes `data/segment_comparison.csv`: each segment's average compared with the FY26 average, and with the average excluding Lead Free DC.
4. `scripts/build_workbook.py` generates the Tableau XML (`.twb`) and packages it with the data into the `.twbx`.

To rebuild everything from the project folder:

```
python -m venv .venv
.venv\Scripts\pip install pandas requests holidays
.venv\Scripts\python scripts\pull_permits.py
.venv\Scripts\python scripts\prepare_permits.py
.venv\Scripts\python scripts\segment_summary.py
.venv\Scripts\python scripts\build_workbook.py
```

## Filters

| Requirement | Implementation |
|---|---|
| Application date on or after Oct 1, 2025 | `ApplicationDate >= 2025-10-01` (applied in the REST query, then re-checked) |
| Only *new* permits | `RenewalDescription = "New"`. Renewals carry a `-R#` suffix on the permit number and are excluded. |
| Issued in FY26 | `IssueDate` between Oct 1, 2025 and Sep 30, 2026 |

## Business days

**How the count works**
- The count runs from the application date to `LastApprovalDate` (the final approval).
- It uses `numpy.busday_count` over calendar dates.
- Saturdays, Sundays and District of Columbia holidays are excluded. The holidays come from `holidays.US(subdiv="DC")`, which includes DC Emancipation Day (April 16) and the observed-date rules.
- A permit approved on the day it was submitted counts as 0.

**The holidays excluded in FY26**

| Date | Holiday |
|---|---|
| Oct 13, 2025 | Indigenous Peoples' Day |
| Nov 11, 2025 | Veterans Day |
| Nov 27, 2025 | Thanksgiving |
| Dec 25, 2025 | Christmas |
| Jan 1, 2026 | New Year's Day |
| Jan 19, 2026 | MLK Jr. Day |
| Feb 16, 2026 | Washington's Birthday |
| Apr 16, 2026 | DC Emancipation Day |
| May 25, 2026 | Memorial Day |
| Jun 19, 2026 | Juneteenth |
| Jul 3, 2026 | Independence Day (observed) |
| Sep 7, 2026 | Labor Day |

**Other time measures:** application to issue, approval to issue, and application to assignment.

13 issued permits have no approval date. They are counted in the permit totals but left out of the approval averages.

## How permit types are categorized (there is no data dictionary)

**Work-type flags.** The TOPS `Is*` flags (`IsExcavation`, `IsFixture`, `IsPaving`, …) give the broad work type. 97% of permits are Excavation, so these flags barely separate anything.

**Line items.** Each permit lists `TypeDetailNames` line items. Three items always appear together on DC Water Lead Free DC permits: Boring Test Pit (Single), Boring Test Pit (Each Add'l), and Repair Water Service Lateral.

**Permit Type Category.** This is the main category, built from the line items:
- Lead Service Line Replacement
- Gas Utility Work
- Water / Sewer Work
- Electric / Telecom Work
- Mega Project
- Other Excavation
- Fixture
- Paving
- Overhead Work
- Landscaping
- Projections

**Applicant Group.** Built from `ApplicantCompany`. DC Water is split by whether the work detail mentions the Lead Free DC program.

## Findings

- **Overall:** 43.8 average business days to approve, median 39. Only 3.3% are approved the same day, and 23.6% take more than 60 business days. The average from application to issuance is 52.3 business days.
- **One program dominates.**
  - DC Water's Lead Free DC lead service line permits are 84% of FY26 new issued permits and average 48.4 business days.
  - All other permits average 19.5 business days.
  - The overall average mostly reflects this one program.
- **By permit type:**

  | Permit type | Avg business days to approve |
  |---|---|
  | Lead service line | 48.3 |
  | Other excavation | 57.8 |
  | Fixtures | 50.0 |
  | Paving | 35.5 |
  | Overhead | 30.0 |
  | Electric/telecom | 25.2 |
  | Water/sewer (non-lead) | 19.1 |
  | Mega projects | 17.7 |
  | Gas | 10.0 |

- **Approval stage vs. issuance stage:**
  - Washington Gas averages 11.5 business days to approval, then 45 more days before issuance (median 3; a long tail of permits sit in "approved, pending payment").
  - So total time to issue for Washington Gas (56.5 days) is in line with everyone else, even though DDOT's review is fast.
- **Timing:**
  - Applications from Oct 2025 to Mar 2026 averaged 65–110 business days. Spring and summer applications averaged 25–40.
  - *Caveat:* later months are right-censored. Only permits already issued by Sep 30 are included, so slow late-year applications are not in the data yet.
- **Geography:** Ward 3 is slowest (60.1) and Ward 8 fastest (28.4).
- **Public Space Committee:** the 61 permits that went to the committee average 72.0 business days.

## Where approval times are meaningfully different
`scripts/segment_summary.py` builds a second, purpose-built data source, `data/segment_comparison.csv`.

**How the comparison works:**
- It compares each segment's average with the comparison average.
- The segments come from these dimensions:
  - permit type
  - applicant
  - program
  - ward
  - quadrant
  - Public Space Committee review
  - application quarter
  - historic district
  - number of line items
- A difference counts as **meaningful** when the segment has at least 30 permits and differs by at least 7 business days, roughly a week and a half.
- The comparison runs twice: against all FY26 permits (average 43.8), and with Lead Free DC excluded (average 19.5).

**Meaningfully slower than the FY26 average:**

| Segment | Avg business days |
|---|---|
| Public Space Committee review | 72.0 |
| FY26 Q1 applications | 71.1 |
| FY26 Q2 applications | 68.9 |
| Ward 3 | 60.1 |
| Other excavation | 57.8 |
| Applicant not recorded | 52.0 |

**Meaningfully faster than the FY26 average:**

| Segment | Avg business days |
|---|---|
| DC Water non-lead work | 5.2 |
| Gas utility work | 10.0 |
| Washington Gas | 11.5 |
| Permits with one line item | 14.2 |
| FY26 Q4 applications | 18.0 |
| Water/sewer | 19.1 |
| Pepco | 23.4 |
| Electric/telecom | 25.2 |
| Ward 8 | 28.4 |
| SE and SW quadrants | about 35 |

**With Lead Free DC excluded (average 19.5):**
- Slower:

  | Segment | Avg business days |
  |---|---|
  | Q2 applications | 75.0 |
  | Committee review | 72.0 |
  | Other excavation | 57.8 |
  | 4+ line items | 52.4 |
  | Private / unrecorded applicants | 50–52 |
  | Fixtures | 50.0 |
  | Telecom | 39.5 |
  | Paving | 35.5 |

- Faster:

  | Segment | Avg business days |
  |---|---|
  | DC Water non-lead work | 5.2 |
  | Gas | 10.0 |
  | Washington Gas | 11.5 |
  | Q4 applications | 9.5 |

- The more complex the permit (more line items, committee review, fixtures, private applicants), the longer it takes.

**Ward is a Lead Free DC effect only:**
- Within Lead Free DC, Ward 3 averages 68.9 and Ward 8 averages 30.2.
- For all other permits, every ward falls between 15 and 24 days.
- So the ward gap reflects how the Lead Free DC queue is handled by ward, not geography in general.

## Suggested next steps
1. Track Lead Free DC permits as their own performance series, so batch submissions don't hide trends for everyone else.
2. Report approval time and approval-to-issuance time separately. The second stage is driven by applicants paying and picking up permits, not by DDOT review.
3. Fix the censoring in the monthly trend by using an application-cohort view that also includes permits still open.
4. Look into how the Lead Free DC queue is handled by ward. Ward 3 Lead Free DC permits take more than twice as long as Ward 8.
5. Look into the Oct 2025–Jan 2026 application backlog.

## Notes and limits
- `LastApprovalDate` is used as the approval date. Permits that were resubmitted are timed from the original application, so applicant revision time is included.
- The workbook XML is generated by script and has been opened and checked in Tableau Desktop 2026.3. The dashboard width adjusts between 1200 and 1600 px, and the height is 1760 px.
