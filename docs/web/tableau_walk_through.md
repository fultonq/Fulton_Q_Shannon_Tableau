# Tableau: DDOT FY26 Permit Approval Analysis

> **Personal prep only. Not part of the submission.** This file is deliberately kept out of `Fulton_Q_Shannon_Tableau.zip`.

All figures come from the TOPS feed as pulled on 2026-10-13. Every number in this guide was computed from that data, including the effect of each alternative method I didn't use.

---

## Part 1 — The 60-second version (memorize this)

> "The Associate Director wanted to know how long new public space construction permits take to approve in FY26, broken down by permit type, plus segments that show where approval times really differ.
>
> I pulled the data from DDOT's TOPS REST service and found the main trap: the feed has one row per **block**, not one per permit. 2,987 permits appear as more than 12,000 rows. Averaging rows gives 41.6 business days, but the correct permit-level answer is **22.2**, about half.
>
> After deduplicating, converting dates to Eastern time, and counting business days without weekends or DC holidays, the median is **13 days**. The distribution has two parts: 22% of permits are approved the same day and 9% take more than 60 days.
>
> The widest gaps are by **resubmission**, at 12 versus 48 days, and **project size**, at 13.5 days for one block versus about 50 for six or more. Resubmitted permits are 27% of permits but 59% of all approval days. Geography makes almost no difference. So the next step I'd recommend is to study why permits get sent back."

---

## Part 2 — The project, in plain terms

| Item | What it means |
|---|---|
| **Client** | Associate Director, Public Space Division (DDOT) |
| **Question** | What is the average number of business days to approve construction permits? How does it vary by permit type? Where do approval times differ? |
| **Explicitly not asked** | Causal explanations or statistical tests. They wanted *segmentation that points to next steps*. |
| **Population** | New permits (not renewals), applied for on or after 10/1/2025, **issued** in FY26 (10/1/2025 – 9/30/2026) |
| **Metric** | Business days from application to approval, excluding weekends and DC holidays |
| **Data** | DDOT TOPS: Public Space Construction Permits (ArcGIS MapServer layer 23), with no data dictionary |
| **Deliverable** | Packaged Tableau workbook with at least 3 sheets and 1 dashboard, plus a narrative |

**What I delivered:**
- A `.twbx` with 10 worksheets and 2 dashboards (main and "Data Segmentation")
- `REPORT_SUMMARY.md`, the findings report
- `README.md`
- A build guide
- 2 Python scripts covering the data pull and data prep

---

## Part 3 — The key numbers (cheat sheet)

| Metric | Value |
|---|---|
| Permits in scope / measured | 2,992 / 2,987 (5 have no approval date) |
| **Average business days to approve** | **22.2** |
| Median | 13 |
| 5% trimmed mean | 18.3 |
| Approved the same day | 22% |
| Approved within 10 business days | 43% |
| More than 60 business days | 9% (279 permits) |
| Average business days to issue | 44.7 (issuance adds about 22.5 after approval; median 3) |
| Calendar days to approve | Average 32.4 / median 20 |

**Segments** (average business days):

| Segment | Fast | Slow |
|---|---|---|
| Resubmission | No: 12.4 (n=2,171) | Yes: 48.3 (n=816) |
| Blocks per permit | 1 block: 13.5 | 6–20: 51.7 · 21+: 45.7 · 2–5: 38.3 |
| Category | Sewer/Storm 0.9 · Gas 8.0 · Electric 21.0 | Multiple Work Types 51.0 · Paving 39.4 · Telecom 37.0 · Water 35.7 |
| Applicant | Washington Gas 8.9 · Pepco 24.6 | Private 44.1 · Gov't 38.7 · Telecom 36.9 · DC Water 31.2 |
| Public Space Committee review | No: 21.3 | Yes: 86.4 (n=41) |
| Ward | Range 18.2 – 27.2 | **Little difference** |

**Share of permits vs. share of approval days:**

| Group | Share of permits | Share of approval days |
|---|---|---|
| Resubmitted | 27% | 59% |
| Water excavation | 32% | 51% |
| Gas excavation | 41% | 15% |

**Where the time goes, by stage** (average business days):

| Stage | Avg business days |
|---|---|
| Application → Ready for Review | 0.4 |
| Ready for Review → Assigned | 1.3 |
| **Assigned → Approved** | **20.6** |
| Approved → Issued | 22.5 (median 3) |

The intake and assignment queue is almost instant. Nearly all of the approval time sits in the review stage, and that stage includes the time applicants spend on resubmissions.

---

## Part 4 — Every key decision: what I chose, why, alternatives, and trade-offs

These are the questions interviewers most often dig into. Each answer includes how much the alternative would have changed the result.

### Decision 1 — Unit of analysis: one row per permit (TrackingNumber)
- **What I found:** 50,649 rows contain only 9,747 unique TrackingNumbers. Each row is a work-location **block**, and one permit has 176 rows. Permit-level fields such as dates and types repeat identically on each row.
- **Choice:** deduplicate to one row per TrackingNumber, and keep the row count as `NumBlockLocations`.
- **Alternative:** average the raw rows. **Impact: 41.6 days instead of 22.2**, because multi-block permits are slower and they dominate the row count. The headline would have been almost double.
- **Alternative:** dedupe on PermitNumber. Unissued permits have no permit number, and a few tracking numbers carry two permit numbers. TrackingNumber is the stable application ID.
- **Trade-off:** in about 89 cases the blocks span several wards. I labeled those "Multiple Wards" rather than splitting them.
- **Why it's a strong talking point:** it shows data skepticism. I checked the grain of the data before calculating anything, and it turned an error that would have doubled the headline into a new segment (project size).

### Decision 2 — What counts as "new"
- **Choice:** `RenewalDescription = "New"`.
- **Alternative:** `PermitTypeDescription = "New"`. It looks right, but it is "New" on most renewals too. **Impact: 5,570 permits instead of 2,992**, an 86% overcount.
- **Evidence:** renewals have permit numbers ending in `-R1`, `-R2`, and so on, plus a `SourcePermit` pointing to the original permit.

### Decision 3 — What counts as "issued in FY26"
- **Choice:** filter `IssueDate` to 10/1/2025 – 9/30/2026, applied together with application date ≥ 10/1/2025.
- **Alternative:** the `FiscalYear` field. Profiling showed it follows the **application** date, not the issue date. **Impact: 3,192 permits**, including some issued after FY26 ended.

### Decision 4 — Start and end of the clock
- **Choice:** Application Date → Last Approval Date.
- **Why:** the brief says "application date," and approval is the point where DDOT's own work ends.
- **Alternative end point:** Issue Date ("days to close"). This gives 44.7 days. Issuance waits on the applicant paying fees, so it mixes DDOT's performance with applicant behavior. I report it as a secondary measure and show the gap on its own sheet.
- **Alternative start points:**
  - ReadyForReviewDate gives 21.8 days, almost the same, because intake takes about 0.4 days.
  - IntakeDate differs from ApplicationDate for about 1,000 records.
  - I followed the brief.
- **Trade-off:** `LastApprovalDate` is the *last* approval, so it absorbs resubmission cycles. That is correct for "time to approve," but it means individual review rounds can't be measured.
- **Note on the brief's wording:** the deliverables section says "days to close" while the rest says "days to approve." I treated approval as primary and showed issuance separately, so both readings are covered.

### Decision 5 — How business days are counted
- **Choice:** count weekdays *after* the application date, up to and including the approval date, minus DC holidays. A same-day approval counts as 0. This equals Excel's `NETWORKDAYS − 1`.
- **Alternatives:**
  - Inclusive NETWORKDAYS, where same-day counts as 1, gives **23.2**. That adds exactly one day to every permit, and "approved same day = 1 day" is counter-intuitive.
  - Removing weekends but not DC holidays also gives **23.2**, so the holidays are worth about 1 day on average.
  - Calendar days give 32.4.
- **Holiday list:** the 13 DC government holidays, including **DC Emancipation Day (4/16)**, which is easy to miss, and observed dates such as July 3, 2026. Inauguration Day doesn't apply in 2026.
- **Implementation choices:**
  - I wrote the calculation **twice**: in Python, stepping through the calendar day by day, and as a Tableau formula. The two match on all 8,479 approved permits, and a `QA Mismatch` field in the workbook proves it.
  - The Tableau formula counts days from a fixed Sunday instead of using `DATEPART('weekday')`, so it doesn't depend on locale or week-start settings.
  - The holidays are hard-coded in the Tableau formula. A holiday table join or relationship would scale better but adds data-model complexity. The trade-off is maintenance: adding FY27 holidays means editing the formula.

### Decision 6 — Time zone
- **Choice:** convert UTC epoch values to America/New_York before taking the date.
- **Impact if skipped:** the headline barely moves (22.13 vs 22.21), but **472 individual permits** get a wrong value, because evening submissions roll over to the next day.
- **Talking point:** a small effect on the average, but it matters for permit-level accuracy and for anyone who checks individual permits in TOPS.

### Decision 7 — Permit type categories (no data dictionary)
- **What I found:** `TypeDetailNames` holds "Family; Detail" pairs, for example "Excavation; Repair Gas Main Line". There are also Is* flags (IsExcavation, IsPaving, and so on). **90% of permits are Excavation.**
- **Choice:** split Excavation by utility (Gas, Water, Sewer/Storm, Electric, Telecom, Test Pit/Boring, Multiple, Other). Keep the other families as they are. Label permits spanning several families "Multiple Work Types".
- **Alternatives:**
  - *Family only* (using the Is* flags): one large Excavation bar averaging 20.1 days hides a range from **0.9 to 37 days** inside it.
  - *Assign a "primary" family* to permits with several families: this needs a priority rule I had no basis for, and it would hide the fact that mixed-scope permits are the slowest group (51 days).
  - *Detail-level* categories: more than 100 detail types, most with tiny counts, are too fragmented to read.
- **Trade-off:** the categories are rule-based and editable in `02_prepare_permits.py`. A test pit bundled with a utility repair is classified by the utility.

### Decision 8 — The "other helpful segment": why applicant type, resubmission, and size
- **Selection criteria:** a big gap (≥10 days or ≥2×), enough permits (n ≥ 20, or flagged as small), a gap that **survives cross-tabs**, and a clear next step.
- **Segments tested:** category, family, applicant, resubmission, block count, Public Space Committee review, ward, quadrant, and application month.
- **Applicant type** is the required third sheet because it is intuitive to an executive. The **cross-tab** sheet then shows it is partly a proxy:
  - Private applicants are asked to resubmit 68% of the time, compared with 12% for Washington Gas.
  - Within each applicant type, resubmission still adds 15 to 35 days.
- **Ward was kept as a negative finding** (18–27 days). Ruling something out is useful for directing the next phase.
- **Application month was kept with a warning.** Its apparent trend is mostly the censoring artifact described in Decision 10.

### Decision 9 — Mean vs. median
- The brief asks for the **average**, so that is the headline. The data is right-skewed (mean 22.2, median 13, 5% trimmed mean 18.3), so I show the median beside every average and include a distribution chart.
- **Why not lead with the median:** it answers a different question than the one asked. The skew is better treated as a finding in its own right: there are two separate service groups.

### Decision 10 — Scope causes survivorship and censoring (the analytic weakness to own)
- The population is defined by **issuance**. Permits applied for late in FY26 are included only if they were issued quickly.
- 1,748 new FY26 applications were **not issued** when the data was pulled: 558 approved but awaiting payment, 506 in revise-and-resubmit, 280 cancelled, and others. The slow, still-pending cases are missing, **so the FY26 average understates the true wait**.
- **Visible effect:** the average by application month falls from about 60 days in February–March to about 5 in August–September. That is an artifact, not improvement.
- **Better alternative for monitoring:** an *application cohort* with a fixed follow-up window (for example, outcome measured 90 business days after application), or survival analysis (Kaplan-Meier), which handles still-open permits properly.
- **Why I didn't do that here:** the brief specified the "issued in FY26" population and said no statistical analysis was needed. I followed the requirement and documented the bias.

### Decision 11 — Tooling: Python prep plus a Tableau calculation
- **Why Python for the data pull and prep:**
  - Tableau has no native ArcGIS REST connector, and Esri's Web Data Connector is deprecated.
  - The server returns at most 2,000 records per request, so the data has to be paged.
  - A script can be re-run and audited.
- **Alternatives:**
  - Download from DC Open Data (manual, and may not match TOPS).
  - Tableau Prep (good for a no-code audience, but harder to version-control).
  - Load into a database such as SQL Server or Postgres with a scheduled refresh (the production answer).
- **Trade-off:** the published CSV is a snapshot. In production I'd schedule the pull and publish a Tableau extract with a refresh schedule.
- **Why the business-day logic lives in Tableau as well:** a reviewer can audit the logic inside the workbook without reading Python, and the Python value serves as an independent check.
- **Building the workbook:** follow `Tableau_Build_Guide.md` in Tableau Desktop and rebuild it yourself before the interview, so you can demo and change any sheet live. Expect requests like "add a filter" or "show me how the business-day calc works"; the ✅ check values in the guide confirm your build matches.

### Decision 12 — Applicant classification
- **Choice:** keyword match on permittee and applicant company (for example "PEPCO", "Pepco", "Potomac Electric Power Company").
- **Alternative:** a maintained master list of applicants or vendors. More accurate, but it doesn't exist in the feed.
- **Trade-off:** a small risk of misclassification within "Private / Other". This is listed as a next step.

---

## Part 5 — The insights, with the "so what"

1. **Two service groups, not one.** 22% of permits are approved the same day, and 9% take more than 60 days. *So what:* set separate targets for routine utility work versus complex or multi-block work. A single average hides both.
2. **Resubmission shows the widest gap.** 27% of permits account for 59% of approval days, and the gap holds within every applicant type. *So what:* the next phase should find out what triggers resubmissions. If incomplete first submissions are the cause, checklists, pre-application meetings and templates for repeat filers are options to test.
3. **Project size matters.** DC Water single-block permits take about 7 days; its multi-block permits take 41–52. *So what:* DC Water isn't "slow" as an applicant; its multi-block lateral-repair work is. *Hypothesis (unconfirmed):* a programmatic replacement effort such as lead service lines. That could justify a program-level or master review approach.
4. **Water excavation is the volume problem.** It is 32% of permits and 51% of approval days. Gas is the reverse: 41% of permits and 15% of approval days.
5. **Public Space Committee review is its own track,** at 86 days versus 21. The sample is small (n=41), but the gap is the largest of any segment.
6. **The review stage is where time goes,** at 20.6 of 22.2 days. Intake and assignment are effectively instant. *So what:* look at reviewer workload and the resubmission loop, not the intake queue.
7. **The post-approval gap belongs to the applicant.** Approval to issue averages 22.5 days but has a median of 3, because a tail of approved permits go unpaid. *So what:* report "DDOT review time" separately from "applicant payment time" on any public-facing measure.
8. **Ward shows little difference.** Wards range from 18 to 27 days. *So what:* don't spend the next phase on location-based analysis.

---

## Part 6 — Likely interview questions and strong answers

**"Walk me through your approach."**
Use the four steps *acquire → understand grain → define the metric → segment*. Lead with the deduplication finding.

**"How did you validate your numbers?"**
- Two independent business-day implementations (Python and Tableau) with 0 mismatches.
- Spot-checks in the TOPS lookup tool.
- Reconciled counts: 50,649 rows, 9,747 permits, 2,992 in scope.
- A worked example: permit `PA404790-R2` applied 10/1 and approved 10/8 is 5 business days (Thursday, Friday, Monday, Tuesday, Wednesday).

**"Why not just use the `DaysToApprove` field in the data?"**
- It counts **calendar** days, not business days.
- Its start point appears to be ReadyForReview, not Application.
- I checked: it matches calendar days from ReadyForReview in most records.
- The brief required business days from the application date.

**"What would you do with more time?"**
1. Reasons for resubmission, from reviewer comments.
2. A stage-by-stage breakdown per review round.
3. Cohort or survival analysis to remove the censoring bias.
4. An automated pipeline and a published extract.
5. Validate the applicant master list.
6. Confirm the DC Water program hypothesis with DC Water and DDOT.

**"What's the biggest weakness of your analysis?"**
Censoring (Decision 10). Own it, explain it, and say how you'd fix it. Interviewers reward this.

**"Is the difference statistically significant?"**
The brief said no statistics were needed. With 816 versus 2,171 permits and a 36-day gap in means (and in medians, 40 vs 7), it would easily pass a Mann-Whitney test. I'd add tests and confidence intervals in a follow-up, especially for small groups like Public Space Committee review (n=41).

**"How would you put this into production?"**
- Scheduled REST pull into a database.
- Holiday calendar as a reference table.
- Tableau Server or Cloud extract with a nightly refresh.
- A data-quality check (row count, deduplication ratio, QA mismatch = 0).
- KPI targets per service track.

**"How did you use AI?"**
Be honest; the brief says AI is expected. Describe it as an accelerator for writing the pull script, drafting calculations and documentation. The judgment calls and validation were yours:
- the grain check
- the New/Renewal field choice
- the FY26 definition
- the cross-validation
- the censoring caveat

Know every decision in Part 4 well enough to defend it without notes.

**"Why is the average different from the median? Which should the Director use?"**
Report both. The average reflects total workload. The median reflects the typical applicant's experience. The gap between them is itself a finding: two service groups.

**"The brief said no explanatory factors. Did you stay within that?"**
Yes, deliberately. Every finding is worded as *where* approval times differ ("resubmitted permits average 48 days vs. 12"), never as *why* ("resubmission causes delays").
- The cross-tabs check whether a gap persists within other segments. That makes the segmentation more useful, but it isn't a causal claim.
- Each segment is paired with a next-step question, such as "what triggers a resubmission?", which is exactly what the brief asked for: segmentation that informs the next steps.
- If pressed: "Proving cause would need more data, such as reviewer comments and submission quality, plus a different design. That's the next phase I'd propose."

Avoid saying "driver" or "factor" in the interview. Use "widest gap", "segment" and "where to look next".

**"Why did you exclude 5 permits?"**
They were issued with no approval date recorded, so the metric can't be computed. Showing them as zero or imputing a value would distort the result. It's documented in the report.

---

## Part 7 — Be ready to demo

1. **Main dashboard, top-left KPI:** 22.2 average and 13 median. Point out the QA = 0 check.
2. **Category chart:** the range inside Excavation (Sewer 0.9 → Water 35.7) is why I split it.
3. **Section 3 (applicant / resubmission / size):** the story of what separates fast from slow.
4. **Data Segmentation dashboard:** the cross-tab showing the resubmission gap in every applicant row, then the Monthly Trend chart to explain the censoring warning.
5. **Click a category** (filter action) to show how the segments change. For example, filter to Water to show the effect of block count.

## Part 8 — Terms to use correctly

| Term | Meaning |
|---|---|
| **Grain** | What one row represents |
| **Censoring / survivorship bias** | Cases with no outcome yet are missing from the data |
| **Cohort** | A group defined by a start event, such as application month |
| **Proxy variable** | A variable that stands in for another; here applicant type partly stands in for resubmission rate and block count |
| **Right-skewed** | A long tail of high values pulls the mean above the median |
| **Business day vs. calendar day** | Business days exclude weekends and holidays |
| **NETWORKDAYS** | The Excel function for counting business days |
| **LOD expression (`FIXED`)** | Tableau's level-of-detail calculation, used for the overall-average reference line |
| **Data source filter vs. worksheet filter** | Context matters: `FIXED` calculations ignore ordinary worksheet filters, which is why the scope logic is also built into the metric itself |
