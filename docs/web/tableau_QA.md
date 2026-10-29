# Interview Q&A: DDOT FY26 Permit Approval Analysis

> **Personal prep only. Not part of the submission.** Practice questions drawn from `Interview_Prep_Guide.md`. Read the question, answer out loud, then check the answer.

All figures match the guide (TOPS feed pulled 2026-10-13).

---

## Section 1 — Opening and framing

### Q: Tell me about this project in one minute.
The Associate Director of the Public Space Division wanted the average business days to approve new public space construction permits in FY26, by permit type, plus segments showing where approval times differ. The feed has one row per **block**, not per permit, so averaging rows gives 41.6 days; the correct permit-level answer is **22.2** (median **13**). The widest gaps are **resubmission** (12 vs. 48 days) and **project size** (13.5 days for one block vs. about 50 for six or more). Resubmitted permits are 27% of permits but 59% of approval days. Ward makes almost no difference. Next step: study why permits get sent back.

### Q: What exactly was the question you were asked?
How many business days, on average, it takes to approve new construction permits issued in FY26; how that varies by permit type; and where approval times differ meaningfully. The client explicitly did **not** ask for causal explanations or statistical tests, but for *segmentation that points to next steps*.

### Q: Who was the audience, and how did that shape your work?
An Associate Director, so an executive audience. I led with one headline number, kept segments intuitive (applicant type is the required third sheet because it reads naturally), showed the median next to every average, and worded every finding as *where* times differ, not *why*.

### Q: What did you deliver?
A `.twbx` with 10 worksheets and 2 dashboards (main and "Deeper Dive"), a findings report (`REPORT_SUMMARY.md`), a README, a Tableau build guide, and 2 Python scripts for the data pull and data prep.

### Q: Walk me through your approach.
Four steps: **acquire → understand grain → define the metric → segment**. Lead with the grain finding: I checked what one row represented before calculating anything, and that kept the headline from being nearly doubled.

---

## Section 2 — Data and grain

### Q: What was the biggest data trap?
The grain. 50,649 rows contain only 9,747 unique TrackingNumbers, because each row is a work-location **block**. One permit has 176 rows. Permit-level fields repeat on every row.

### Q: What would have happened if you had averaged the raw rows?
The average would be **41.6** business days instead of **22.2**. Multi-block permits are slower and dominate the row count, so the headline would have been almost double.

### Q: Why dedupe on TrackingNumber rather than PermitNumber?
Unissued permits have no permit number, and a few tracking numbers carry two permit numbers. TrackingNumber is the stable application ID. I kept the row count as `NumBlockLocations`, which became the project-size segment.

### Q: How did you handle permits whose blocks span several wards?
About 89 permits span more than one ward. I labeled them "Multiple Wards" rather than splitting them across wards.

### Q: How did you define a "new" permit?
`RenewalDescription = "New"`. The obvious-looking field, `PermitTypeDescription`, says "New" on most renewals too; using it gives 5,570 permits instead of 2,992, an 86% overcount. The evidence: renewals have permit numbers ending `-R1`, `-R2`, and a `SourcePermit` pointing to the original.

### Q: How did you define "issued in FY26"?
`IssueDate` between 10/1/2025 and 9/30/2026, together with application date on or after 10/1/2025. The `FiscalYear` field follows the **application** date, not the issue date; using it gives 3,192 permits, including some issued after FY26 ended.

### Q: How many permits are in scope, and why are 5 missing from the metric?
2,992 in scope, 2,987 measured. The 5 were issued with no approval date recorded, so the metric can't be computed. Showing them as zero or imputing a value would distort the result; it's documented in the report.

### Q: There was no data dictionary. How did you work out what fields meant?
By profiling: comparing fields against each other (for example, `FiscalYear` against application and issue dates, `PermitTypeDescription` against `RenewalDescription` and `-R` suffixes), checking repeated values across block rows, and spot-checking individual permits in the TOPS lookup tool.

### Q: Why didn't you just use the `DaysToApprove` field?
It counts **calendar** days, and its start point appears to be ReadyForReview, not Application. I checked: it matches calendar days from ReadyForReview in most records. The brief required business days from the application date.

---

## Section 3 — The metric

### Q: Where does the clock start and stop?
Application Date → Last Approval Date. The brief says "application date," and approval is where DDOT's own work ends.

### Q: Why not measure to the issue date?
Issuance waits on the applicant paying fees, so it mixes DDOT's performance with applicant behavior. Days to issue averages 44.7. I report it as a secondary measure and show the gap on its own sheet.

### Q: The brief says both "days to close" and "days to approve." Which did you use?
Approval as primary, issuance shown separately, so both readings are covered.

### Q: What about other start points?
ReadyForReviewDate gives 21.8 days, almost the same, because intake takes about 0.4 days. IntakeDate differs from ApplicationDate for about 1,000 records. I followed the brief.

### Q: What's the limitation of using LastApprovalDate?
It's the *last* approval, so it absorbs resubmission cycles. That's correct for "time to approve," but individual review rounds can't be measured.

### Q: How exactly do you count business days?
Weekdays *after* the application date, up to and including the approval date, minus DC holidays. Same-day approval = 0. It equals Excel's `NETWORKDAYS − 1`.

### Q: Why not inclusive NETWORKDAYS?
It gives 23.2, adding exactly one day to every permit, and "approved the same day = 1 day" is counter-intuitive.

### Q: How much do the DC holidays matter?
About 1 day on average: weekends-only gives 23.2 vs. 22.2. The list is the 13 DC government holidays, including **DC Emancipation Day (4/16)**, which is easy to miss, and observed dates such as July 3, 2026. Inauguration Day doesn't apply in 2026.

### Q: Give me a worked example.
Permit `PA404790-R2`, applied 10/1 and approved 10/8, is 5 business days: Thursday, Friday, Monday, Tuesday, Wednesday.

### Q: How did you handle time zones, and did it matter?
I converted UTC epoch values to America/New_York before taking the date. The headline barely moves (22.13 vs. 22.21), but **472 permits** would otherwise get a wrong value because evening submissions roll into the next day. It matters for anyone checking individual permits in TOPS.

### Q: Why lead with the mean when the data is skewed?
The brief asks for the **average**. Mean 22.2, median 13, 5% trimmed mean 18.3, so I show the median beside every average and include a distribution chart. Leading with the median would answer a different question. The skew is a finding in its own right: two service groups.

### Q: Which should the Director use, mean or median?
Both. The average reflects total workload; the median reflects the typical applicant's experience. The gap between them is itself a finding.

---

## Section 4 — Validation and Tableau

### Q: How did you validate your numbers?
- Two independent business-day implementations (Python day-by-day and a Tableau formula) with 0 mismatches across all 8,479 approved permits; a `QA Mismatch` field in the workbook proves it.
- Spot-checks in the TOPS lookup tool.
- Reconciled counts: 50,649 rows → 9,747 permits → 2,992 in scope.
- A hand-worked example (`PA404790-R2`, 5 business days).

### Q: How does the Tableau business-day formula work?
It counts days from a fixed Sunday instead of using `DATEPART('weekday')`, so it doesn't depend on locale or week-start settings. The DC holidays are hard-coded and subtracted when they fall in the window.

### Q: Why hard-code holidays instead of a holiday table?
A join or relationship would scale better but adds data-model complexity. The trade-off is maintenance: adding FY27 holidays means editing the formula. In production I'd use a reference table.

### Q: Why compute business days in both Python and Tableau?
A reviewer can audit the logic inside the workbook without reading Python, and the Python value is an independent check.

### Q: Why use Python for the data pull at all?
Tableau has no native ArcGIS REST connector, Esri's Web Data Connector is deprecated, and the server returns at most 2,000 records per request, so the data has to be paged. A script can also be re-run and audited.

### Q: What alternatives to Python did you consider?
DC Open Data download (manual, may not match TOPS), Tableau Prep (good for no-code audiences, harder to version-control), or a database such as SQL Server or Postgres with a scheduled refresh, which is the production answer.

### Q: Where did you use an LOD expression?
A `FIXED` LOD for the overall-average reference line. Because `FIXED` ignores ordinary worksheet filters, the scope logic is also built into the metric itself, not left to a worksheet filter.

### Q: Show me how the business-day calc works. / Add a filter.
Be ready to do this live. Rebuild the workbook from `Tableau_Build_Guide.md` before the interview and use the ✅ check values to confirm your build matches.

---

## Section 5 — Segments and findings

### Q: How did you categorize permit types without a data dictionary?
`TypeDetailNames` holds "Family; Detail" pairs. 90% of permits are Excavation, so I split Excavation by utility (Gas, Water, Sewer/Storm, Electric, Telecom, Test Pit/Boring, Multiple, Other), kept other families as they were, and labeled permits spanning several families "Multiple Work Types."

### Q: Why not just use the work-type family?
One Excavation bar averaging 20.1 days hides a range from **0.9 to 37 days**. Detail-level categories (100+ types, mostly tiny counts) are too fragmented, and assigning a "primary" family needs a priority rule I had no basis for, and would hide that mixed-scope permits are slowest (51 days).

### Q: How did you choose which segments to show?
Criteria: a big gap (≥10 days or ≥2×), enough permits (n ≥ 20, or flagged), a gap that **survives cross-tabs**, and a clear next step. I tested category, family, applicant, resubmission, block count, Public Space Committee review, ward, quadrant and application month.

### Q: What's the single most important finding?
Resubmission: 12.4 days (n=2,171) vs. 48.3 (n=816). Resubmitted permits are 27% of permits but 59% of approval days, and the gap holds within every applicant type.

### Q: Isn't applicant type the real story? Private applicants are much slower.
Partly a proxy. Private applicants are asked to resubmit 68% of the time vs. 12% for Washington Gas. Within each applicant type, resubmission still adds 15 to 35 days. The cross-tab sheet on the Deeper Dive dashboard shows this.

### Q: What does project size tell you?
1 block: 13.5 days; 2–5: 38.3; 6–20: 51.7; 21+: 45.7. DC Water single-block permits take about 7 days, its multi-block permits 41–52. So DC Water isn't slow as an applicant; its multi-block lateral-repair work is. *Unconfirmed hypothesis:* a programmatic effort such as lead service line replacement, which could justify a program-level review approach.

### Q: Which permit categories are fastest and slowest?
Fast: Sewer/Storm 0.9, Gas 8.0, Electric 21.0. Slow: Multiple Work Types 51.0, Paving 39.4, Telecom 37.0, Water 35.7.

### Q: Where is the volume problem?
Water excavation: 32% of permits, 51% of approval days. Gas is the reverse: 41% of permits, 15% of approval days.

### Q: What about Public Space Committee review?
86.4 days vs. 21.3, the largest gap of any segment, but small (n=41). I'd add confidence intervals before acting on it.

### Q: Does location matter?
Very little. Wards range from 18.2 to 27.2 days. I kept ward as a **negative finding**: ruling something out tells the next phase where not to spend effort.

### Q: Where does the time go by stage?
Application → Ready for Review 0.4; Ready for Review → Assigned 1.3; **Assigned → Approved 20.6**; Approved → Issued 22.5 (median 3). Intake is near-instant; nearly all approval time is in review, which includes applicant resubmission time.

### Q: Why is approval-to-issue so long on average but the median only 3?
A tail of approved permits go unpaid. That time belongs to the applicant, so any public measure should separate "DDOT review time" from "applicant payment time."

### Q: Describe the distribution.
Two service groups: 22% are approved the same day, 43% within 10 business days, and 9% (279 permits) take more than 60. A single average hides both, so I'd set separate targets for routine utility work vs. complex or multi-block work.

---

## Section 6 — Weaknesses and pushback

### Q: What's the biggest weakness of your analysis?
Censoring / survivorship. The population is defined by **issuance**, so late-FY26 applications are included only if they were issued quickly. 1,748 new FY26 applications weren't issued at pull time (558 approved awaiting payment, 506 in revise-and-resubmit, 280 cancelled, others). The slow pending cases are missing, so **the FY26 average understates the true wait**.

### Q: How does that show up in the dashboard?
Average by application month falls from about 60 days in February–March to about 5 in August–September. That's an artifact, not improvement. I kept the chart with a warning.

### Q: How would you fix it?
An *application cohort* with a fixed follow-up window (for example, outcome measured 90 business days after application), or survival analysis (Kaplan-Meier), which handles still-open permits properly.

### Q: Then why didn't you?
The brief specified the "issued in FY26" population and said no statistical analysis was needed. I followed the requirement and documented the bias.

### Q: Is the resubmission difference statistically significant?
The brief said no statistics were needed. With 816 vs. 2,171 permits and a 36-day gap in means (medians 40 vs. 7), it would easily pass a Mann-Whitney test. I'd add tests and confidence intervals in a follow-up, especially for small groups like Public Space Committee review (n=41).

### Q: The brief said no explanatory factors. Did you stay within that?
Yes. Every finding is worded as *where* times differ, never *why*. Cross-tabs check whether a gap persists within other segments, which isn't a causal claim. Each segment is paired with a next-step question. If pressed: proving cause would need reviewer comments and submission-quality data plus a different design; that's the next phase I'd propose. (Avoid "driver" and "factor"; say "widest gap," "segment," "where to look next.")

### Q: How confident are you in the applicant classification?
It's a keyword match on permittee and applicant company (for example "PEPCO", "Potomac Electric Power Company"). A maintained master list would be more accurate but doesn't exist in the feed. Small misclassification risk within "Private / Other"; validating it is a listed next step.

### Q: How did a test pit bundled with a utility repair get classified?
By the utility. The category rules are explicit and editable in `02_prepare_permits.py`.

---

## Section 7 — Next steps and production

### Q: What would you do with more time?
1. Reasons for resubmission, from reviewer comments.
2. Stage-by-stage breakdown per review round.
3. Cohort or survival analysis to remove censoring bias.
4. An automated pipeline and published extract.
5. Validate the applicant master list.
6. Confirm the DC Water program hypothesis with DC Water and DDOT.

### Q: How would you put this into production?
Scheduled REST pull into a database; holiday calendar as a reference table; Tableau Server or Cloud extract with a nightly refresh; data-quality checks (row count, dedup ratio, QA mismatch = 0); KPI targets per service track.

### Q: What would you recommend to the Director tomorrow?
Study what triggers resubmissions. If incomplete first submissions are the cause, test checklists, pre-application meetings and templates for repeat filers. Set separate targets for routine vs. complex work, and report DDOT review time separately from applicant payment time.

### Q: How did you use AI?
Honestly: the brief says AI is expected. It accelerated writing the pull script, drafting calculations and documentation. The judgment calls and validation were mine: the grain check, the New/Renewal field choice, the FY26 definition, the cross-validation, and the censoring caveat.

---

## Section 8 — Rapid-fire numbers drill

| Question | Answer |
|---|---|
| Average business days to approve | 22.2 |
| Median | 13 |
| 5% trimmed mean | 18.3 |
| Average if you averaged raw rows | 41.6 |
| Raw rows / unique permits | 50,649 / 9,747 |
| Permits in scope / measured | 2,992 / 2,987 |
| Approved same day | 22% |
| Approved within 10 business days | 43% |
| Over 60 business days | 9% (279) |
| Days to issue (avg) | 44.7 |
| Calendar days to approve (avg / median) | 32.4 / 20 |
| Resubmitted vs. not | 48.3 vs. 12.4 |
| Resubmitted share of permits / approval days | 27% / 59% |
| 1 block vs. 6–20 blocks | 13.5 vs. 51.7 |
| PSC review vs. not | 86.4 vs. 21.3 (n=41) |
| Ward range | 18.2 – 27.2 |
| Assigned → Approved stage | 20.6 |
| Permits with wrong date if UTC kept | 472 |
| Overcount using PermitTypeDescription | 5,570 (86%) |
| Count using FiscalYear field | 3,192 |
| Unissued FY26 new applications | 1,748 |
