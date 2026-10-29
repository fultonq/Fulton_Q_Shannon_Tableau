# FY2026 Public Space Construction Permits — Approval Time Analysis

**Prepared for:** Associate Director, Public Space Division
**Prepared by:** Analytics, Assets, and Performance Branch
**Data as of:** October 13, 2026 (DDOT TOPS REST feed, layer 23)
**Deliverable:** Tableau packaged workbook `FY26_Public_Space_Permit_Approvals.twbx`

## 1. Executive Summary

**New public space construction permits issued in FY26 took an average of 22.2 business days to approve (median 13).** The average describes very few permits, because the distribution has two separate parts:

- **A fast lane.** 22% of permits were approved the same day, and 43% within 10 business days. These are almost all routine single-block utility jobs, such as gas service work, sewer cleanouts and emergency water main repairs.
- **A slow lane.** 9% of permits took more than 60 business days. These were mostly multi-block DC Water projects and permits that DDOT sent back for revisions.

Five segments show meaningfully different approval times. The first two cover most of the total approval workload:

| # | Segment | Fast group | Slow group | Gap |
|---|---|---|---|---|
| 1 | **Resubmission requested** | No: **12.4 days** | Yes: **48.3 days** | **~4×** |
| 2 | **Work-location size (blocks)** | 1 block: **13.5** | 6–20 blocks: **51.7** | **~4×** |
| 3 | **Permit category** | Sewer/Storm: **0.9**, Gas: **8.0** | Multiple work types: **51.0**, Paving: **39.4** | up to 50 days |
| 4 | **Applicant type** | Washington Gas: **8.9** | Private / Other: **44.1** | ~5× |
| 5 | **Public Space Committee review** | No: **21.3** | Yes: **86.4** (n=41) | ~4× |
| — | **Ward** (for comparison) | 18.2 | 27.2 | **small gap** |

**Main point:** the widest gaps are between permits that were sent back for resubmission and those that weren't, and between single-block and multi-block permits. Those gaps persist within every applicant type. Ward and quadrant show little difference. Resubmitted permits make up **27% of permits but 59% of all business days spent in approval**.

*As the brief specifies, these are segments showing **where** approval times differ, not explanations of **why**. Each one points to a question worth exploring next.*

## 2. Scope and Definitions

| Item | Definition used |
|---|---|
| Population | Permits with `RenewalDescription = "New"`, **application date on or after 10/1/2025**, and **issue date between 10/1/2025 and 9/30/2026** |
| Unit of analysis | **One permit (TrackingNumber).** The raw feed has one row per work block, so it was deduplicated. |
| Approval time | Business days from **Application Date** to **Last Approval Date** |
| Business day | A weekday that isn't a DC government holiday. Counting starts the day after application and includes the approval day, so a same-day approval counts as 0. This equals `NETWORKDAYS − 1`. |
| Holidays excluded | 10/13/25, 11/11/25, 11/27/25, 12/25/25, 1/1/26, 1/19/26, 2/16/26, **4/16/26 (DC Emancipation Day)**, 5/25/26, 6/19/26, 7/3/26 (observed), 9/7/26 |
| Final count | **2,992 permits in scope. 2,987 have an approval date and are measured.** The 5 without one are excluded. |

## 3. Approach and Methodology

### 3.1 Data acquisition
The ArcGIS MapServer limits each request to 2,000 records. `scripts/01_pull_permits.py` therefore requests every record with an application date on or after 10/1/2025, ordered by OBJECTID and paged 2,000 records at a time, with retries. The result was 50,649 rows.

**Why this approach:** Tableau Desktop doesn't connect natively to ArcGIS REST, and the old Esri Web Data Connector is deprecated. A scripted pull can be repeated, can be audited, and returns every field. Filtering on the server by application date keeps the download small without dropping any record that could qualify.

### 3.2 Data exploration (there was no data dictionary)
I worked out the meaning of each field by profiling the data and checking individual permits against the TOPS lookup tool:

| Question | Evidence | Decision |
|---|---|---|
| What is one row? | 50,649 rows contain only 9,747 unique TrackingNumbers. One permit has 176 rows, each with a different block address. Permit-level fields such as dates and types are repeated identically on every row (more than 99.9% consistent). | **Deduplicate to one row per TrackingNumber.** The block count is kept as a new segment. Averaging raw rows would weight a 176-block permit 176 times. |
| How do I identify a "new" permit? | `RenewalDescription` has two values: New (23,006 rows) and Renewal (27,643 rows). Renewal permit numbers end in "-R1", "-R2", and so on, and have a `SourcePermit`. `PermitTypeDescription` is "New" on 86% of rows, including renewals. | Use **`RenewalDescription`**. |
| What does "issued in FY26" mean? | `FiscalYear` follows the **application** date (for example, applications from Oct 2026 are FY2027). It doesn't reflect the issue date. | Filter on **`IssueDate`** directly. |
| Which time zone are the dates in? | Dates are stored as UTC epoch values. Applications submitted after 8 PM Eastern would otherwise move to the next calendar day. | Convert every date to **America/New_York** before taking the date part. |
| Which date marks approval? | The built-in `DaysToApprove` matches calendar days from `ReadyForReviewDate` to `LastApprovalDate`. `IssueDate` comes after fee payment, and approval never comes after issuance. | Use **Application → LastApprovalDate**, as the brief specifies the application date. Application → Issue is reported as a secondary measure. |
| How should permit types be categorized? | `TypeDetailNames` holds "Family; Detail" pairs. **90% of permits are Excavation**, so a family-only view would be one large bar plus a few small ones. | Excavation is split by **utility type** (Gas, Water, Sewer/Storm, Electric, Telecom, Test Pit/Boring, Multiple, Other). Paving, Fixture, Over Head Work, Landscaping and Projections stay as their own groups. Permits that span several families are labeled **Multiple Work Types**. |

### 3.3 Business-day calculation
The calculation is implemented twice, independently:
1. **In Python** (`02_prepare_permits.py`), stepping through the calendar day by day and saved as `BusinessDaysToApprove_QA`.
2. **In Tableau**, with a closed-form formula that doesn't depend on locale: a weekday index measured from a fixed Sunday (1/1/2023), minus the number of holidays in the interval.

The two give **identical results for all 8,479 approved permits**, with 0 mismatches. A `QA Mismatch` field in the workbook demonstrates this.

**Why build it in Tableau as well as precomputing it:** the reviewer can see and audit the logic in the workbook itself, and the Python column provides an independent check.

### 3.4 Segmentation approach
The brief asks for segmentation, not explanatory statistics. I looked at **average, median and permit count** for each candidate segment, and kept segments that met all of these tests:

- the gap between groups is large (≥10 business days, or ≥2×)
- the groups have enough permits (n ≥ 20, or flagged when smaller)
- the gap **holds within other segments** (cross-tabs), so it isn't just a side effect of a different mix of permits
- the segment points to a clear next step

Segments tested: permit category, work family, applicant type, resubmission requested, block count, Public Space Committee review, ward, quadrant, and application month.

Medians are shown next to averages throughout, because the data is strongly right-skewed: the mean is 22 and the median is 13.

## 4. Key Data Insights

### Insight 1 — The overall average combines a fast group and a slow group
| Measure | Value |
|---|---|
| Average business days to approve | **22.2** |
| Median | **13** |
| Approved the same day (0 days) | **22%** (664 permits) |
| Approved within 10 business days | **43%** |
| More than 60 business days | **9%** (279 permits) |
| Average business days to *issue* | **44.7** |

The same-day group is almost entirely Washington Gas (458) and DC Water (199): routine gas work, sewer cleanouts and **water main repairs, which are approved in about 1 day** and are likely emergency work. The group above 60 days is **76% resubmitted permits and 63% DC Water**. No single "typical" approval time describes this distribution, so performance targets should be set separately for each group.

### Insight 2 — Resubmission shows the widest gap in approval times
| | Permits | Avg days | Median | Share of all approval days |
|---|---|---|---|---|
| No resubmission requested | 2,171 (73%) | **12.4** | 7 | 41% |
| Resubmission requested | 816 (27%) | **48.3** | 40 | **59%** |

The difference **holds in every applicant type, and in every permit category that has at least 15 resubmitted permits**:

| Applicant | No resubmission | Resubmission | Added days |
|---|---|---|---|
| Washington Gas | 5.5 | 33.6 | +28 |
| DC Water | 19.6 | 54.9 | +35 |
| Private / Other | 20.3 | 55.2 | +35 |
| Pepco | 18.0 | 33.2 | +15 |

**Private applicants are asked to resubmit 68% of the time**, compared with 12% for Washington Gas, so the applicant and resubmission segments overlap heavily. Within each applicant type, private permits without a resubmission average 20.3 days, close to DC Water (19.6) and Pepco (18.0).

**Where to look next:** resubmitted permits hold 59% of all approval days, so understanding what triggers a resubmission is the most valuable next question. If incomplete first submissions turn out to be the cause, checklists, pre-application guidance and templates for repeat filers are options to test.

### Insight 3 — Project size (number of blocks) shows the second widest gap
| Blocks per permit | Permits | Avg days |
|---|---|---|
| 1 block | 2,200 | **13.5** |
| 2–5 blocks | 233 | 38.3 |
| 6–20 blocks | 403 | **51.7** |
| 21+ blocks | 151 | 45.7 |

The pattern is clearest within DC Water. Its single-block permits average **7.1 days (median 1)**. Its multi-block permits average **41–52 days**. Water excavation shows the same pattern: 9.4 days for 1 block and 52.0 days for 6–20 blocks.

**DC Water's high average is concentrated in its multi-block permits; its single-block permits are among the fastest.** The multi-block permits are largely "Repair Water Service Lateral" bundled with boring test pits (791 permits, 42 days on average). This looks like a programmatic lateral-replacement effort; the program link is not yet confirmed.

### Insight 4 — Permit category: routine utility work is fast, while complex or mixed work is slow
| Fastest | Avg | Slowest (n ≥ 20) | Avg |
|---|---|---|---|
| Excavation – Sewer/Storm | **0.9** | Multiple Work Types | **51.0** |
| Excavation – Gas | **8.0** | Paving | 39.4 |
| Excavation – Electric | 21.0 | Excavation – Telecom | 37.0 |
| Excavation – Other | 21.5 | Excavation – Multiple Utilities | 36.3 |
| | | Excavation – Water | 35.7 |

- **Water excavation alone accounts for 51% of all approval business days** while being 32% of permits.
- Gas is the opposite case: **41% of permits but only 15% of approval days**.
- **Multiple Work Types** permits (for example paving, fixtures and landscaping together, as in streetscape projects) are the slowest group of meaningful size. When they need resubmission they average **67.5 days**.
- Landscaping (52.8) and Projections (35.9) each have only 9 permits, so these figures are indicative only.

### Insight 5 — Applicant type: the gaps overlap with what each applicant files
| Applicant | Permits | Avg | Median |
|---|---|---|---|
| Washington Gas | 1,316 | **8.9** | 3 |
| Pepco | 193 | 24.6 | 17 |
| DC Water | 1,132 | 31.2 | 26 |
| Telecom (Verizon, Comcast, Crown Castle, …) | 77 | 36.9 | 27 |
| Government agencies | 23 | 38.7 | 19 |
| Private / Other | 246 | **44.1** | 28 |

Washington Gas files single-block, single-type permits with few resubmissions. Private applicants file varied work types and are asked to resubmit often. Applicant type is a useful way to see the pattern, but **the cross-tabs show the applicant gaps largely line up with differences in resubmission rate and block count**. That suggests segmenting by those two first in the next phase.

### Insight 6 — Permits with Public Space Committee review average about 65 days longer
The 41 permits that went through Public Space Committee review averaged **86.4 business days**, compared with 21.3 for the rest. The group is small, but the gap is the largest of any segment. These permits should be tracked as their own service track with a separate target.

### Insight 7 — Time after approval is a separate issue
Issuance adds about **22 business days on average** after approval (average days to issue is 44.7, compared with 22.2 to approve). This period depends on the applicant paying fees, not on DDOT's review. For gas permits the *average* is 55 days to issue but the *median* is 22. A tail of permits that were approved but not paid for creates that gap. **Any public-facing time-to-permit measure should separate "DDOT review time" from "applicant payment time."**

### Insight 8 — Geography isn't a meaningful differentiator
Ward averages fall in a narrow 18–27 day range, and quadrant averages range from 17 to 24. This negative result is useful: deeper analysis should **not** focus on location.

### Insight 9 — Don't read the monthly trend at face value
By application month, averages drop from about 60 days (Feb–Mar 2026) to about 5 days (Aug–Sep 2026). **This is mostly a cut-off effect.** A permit applied for in September counts only if it was issued by September 30, so only the fast ones are included. A fair trend needs cohort tracking. See next step 4.

## 5. Limitations

- **Survivorship and censoring:** only permits *issued* in FY26 are included. Slow permits applied for late in the year that are still pending are left out, which pulls the averages down.
- **Last approval date:** reapprovals overwrite earlier approvals, so time spent on the first review can't be separated from later reviews.
- **Small groups:** Landscaping, Projections, Government Agency and Public Space Committee review each have fewer than 50 permits.
- **Categorization is rule-based:** the categories come from text in `TypeDetailNames`. The rules are documented in `scripts/02_prepare_permits.py` and can be adjusted.
- **No causal claims:** following the brief, the segments show *where* approval times differ, not *why*.
- **Fixed data snapshot:** all figures come from the 2026-10-13 pull, which is committed as `data/raw/permits_raw.json.gz`. The live feed later drops some permits: a re-pull on 2026-10-29 was missing 460 of the 2,992 in-scope permits (94% of all dropped permits had status "Permit Expired", mostly applied for in June–July 2026). The loss falls mostly on quick approvals (Washington Gas lost 309 of its 1,316 permits), so re-pulling would push the average up from 22.2 to 24.2 business days without any change in performance. The snapshot is kept for that reason. The segment rankings and the largest gaps were the same in the re-pull.
