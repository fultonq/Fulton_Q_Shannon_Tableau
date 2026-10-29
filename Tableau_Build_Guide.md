# FY26 Public Space Construction Permits: Tableau Build Guide

This guide walks through building `FY26_Public_Space_Permit_Approvals.twbx` from scratch in **Tableau Desktop**. Every calculated field, worksheet, dashboard and setting in the delivered workbook is covered, with the expected values for checking each step.

**Assignment requirements** (from the brief):

1. A worksheet with the average business days to approve
2. A worksheet with the average business days by permit type category
3. A worksheet with another segment that shows where approval times differ
4. A dashboard with a structured layout, a title, section titles, and guiding text

**What you'll build:**
- 1 data source
- 20 calculated fields
- 10 worksheets
- 2 dashboards
- 1 filter action

Allow about 2–3 hours. The data was pulled from the DDOT TOPS REST feed on 2026-10-13.

---

## 0. Before you start

| File | Purpose |
|---|---|
| `data/permits_by_tracking_number.csv` | **The data source.** One row per permit (TrackingNumber), covering all 9,747 permits applied for on or after 10/1/2025. |
| `data/dc_holidays.csv` | DC government holidays used in the business-day calculation (for reference) |
| `scripts/01_pull_permits.py`, `scripts/02_prepare_permits.py` | Re-pull and re-prepare the data (optional; see README §6) |

**How to use this guide:**
- Work through the sections in order, because later formulas refer to earlier fields by name.
- Copy calculated-field names **exactly**.
- After each worksheet, compare against the ✅ **Check** values.

---

## 1. What the data exploration showed

There's no data dictionary, so these decisions came from profiling the feed. They explain why the data source looks the way it does.

| Finding | Why it matters | How it's handled |
|---|---|---|
| **The raw feed has one row per work-location block, not one per permit.** 50,649 rows cover only 9,747 tracking numbers, and one permit has 176 rows. | Averaging raw rows gives **41.6** days instead of **22.2**, because large multi-block permits get counted many times. | The CSV has **one row per TrackingNumber**. `NumBlockLocations` keeps the block count, which becomes a segment. |
| **"New" is stored in `RenewalDescription`** (New / Renewal). `PermitTypeDescription` says "New" even on renewals. | The wrong field would include renewals: 5,570 permits instead of 2,992. | Filter on `NewOrRenewal = "New"`. |
| **"Issued in FY26" has to use `IssueDate`.** The `FiscalYear` field follows the *application* date. | Filtering on `FiscalYear` gives the wrong population. | Filter `IssueDate` to 10/1/2025 – 9/30/2026. |
| **Dates are stored in UTC.** | Evening submissions would roll over to the next day, giving 472 permits a wrong value. | Dates are converted to Eastern time before the date is taken. |
| **Approval vs. issuance.** `ApprovalDate` is DDOT's final approval. `IssueDate` comes after the applicant pays the fees. | "Days to approve" measures DDOT's review. "Days to issue" adds time the applicant controls. | **Primary: Application → Approval.** Secondary: Application → Issue. |
| **Permit types** are "Family; Detail" pairs, and 90% of permits are Excavation. | A family-only view hides a 0.9 to 37 day range inside Excavation. | `PermitCategory` splits Excavation by utility. `WorkTypeFamily` keeps the top-level family. |

**Scope:** 2,992 new permits applied for on or after 10/1/2025 and issued in FY26. **2,987** have an approval date and are measured.

**Business-day rule:** count the weekdays *after* the application date, up to and including the approval date, skipping DC holidays. A same-day approval counts as 0. This equals Excel's `NETWORKDAYS(start, end, holidays) − 1`.

DC holidays excluded:

| Date | Holiday |
|---|---|
| 10/13/25 | Indigenous Peoples' Day |
| 11/11/25 | Veterans Day |
| 11/27/25 | Thanksgiving |
| 12/25/25 | Christmas |
| 1/1/26 | New Year's Day |
| 1/19/26 | Martin Luther King Jr. Day |
| 2/16/26 | Washington's Birthday |
| **4/16/26** | **DC Emancipation Day** |
| 5/25/26 | Memorial Day |
| 6/19/26 | Juneteenth |
| 7/3/26 | Independence Day (observed) |
| 9/7/26 | Labor Day |
| 10/12/26 | Indigenous Peoples' Day |

---

## 2. Connect to the data

1. Open **Tableau Desktop**. On the start page, under **Connect → To a File**, choose **Text file**. Select `data/permits_by_tracking_number.csv`.
2. On the **Data Source** page, check the type icon above each column in the preview grid, and click an icon to change it:

   | Column | Set type to |
   |---|---|
   | `TrackingNumber` | **String** (it's an ID; Tableau may detect it as a number) |
   | `ApplicationDate`, `ApprovalDate`, `IssueDate` | **Date** |
   | `Ward` | **String** |
   | `Latitude`, `Longitude` | Number (decimal) |

3. Rename the data source: double-click the name in the top-left corner and type **`FY26 Permits`**.
4. Leave the connection on **Live** for now. Change it to **Extract** at the end (§7).
5. Click **Sheet 1** to start building.

> **Tip:** In the Data pane, right-click `TrackingNumber` → **Convert to Dimension** if Tableau shows it under Measures.

---

## 3. Calculated fields

Create each field with **Analysis → Create Calculated Field…**. Type the name exactly as shown, paste the formula, and click **OK**.

**Optional tidy-up:** select the fields in the Data pane, then right-click → **Folders → Create Folder**. For example, use "Business Day Logic" for 3.1–3.10 and "KPIs" for 3.11–3.20.

### 3.1 `In Scope (FY26 New Issued)`
```
[NewOrRenewal] = "New"
AND [ApplicationDate] >= #2025-10-01#
AND [IssueDate] >= #2025-10-01#
AND [IssueDate] <= #2026-09-30#
```

### 3.2 `Weekday Index - Application`
This counts weekdays since Sunday 1/1/2023. Using `DATEDIFF` from a fixed Sunday, instead of `DATEPART('weekday')`, gives the same result whatever the locale or week-start setting.
```
5 * INT(DATEDIFF('day', #2023-01-01#, [ApplicationDate]) / 7)
+ MIN(DATEDIFF('day', #2023-01-01#, [ApplicationDate]) % 7, 5)
```

### 3.3 `Weekday Index - Approval`
```
5 * INT(DATEDIFF('day', #2023-01-01#, [ApprovalDate]) / 7)
+ MIN(DATEDIFF('day', #2023-01-01#, [ApprovalDate]) % 7, 5)
```

### 3.4 `Weekday Index - Issue`
```
5 * INT(DATEDIFF('day', #2023-01-01#, [IssueDate]) / 7)
+ MIN(DATEDIFF('day', #2023-01-01#, [IssueDate]) % 7, 5)
```

### 3.5 `Holidays - Application to Approval`
This counts the DC holidays that fall after the application date and on or before the approval date. Every date listed falls on a weekday.
```
IIF(#2025-10-13# > [ApplicationDate] AND #2025-10-13# <= [ApprovalDate], 1, 0) +
IIF(#2025-11-11# > [ApplicationDate] AND #2025-11-11# <= [ApprovalDate], 1, 0) +
IIF(#2025-11-27# > [ApplicationDate] AND #2025-11-27# <= [ApprovalDate], 1, 0) +
IIF(#2025-12-25# > [ApplicationDate] AND #2025-12-25# <= [ApprovalDate], 1, 0) +
IIF(#2026-01-01# > [ApplicationDate] AND #2026-01-01# <= [ApprovalDate], 1, 0) +
IIF(#2026-01-19# > [ApplicationDate] AND #2026-01-19# <= [ApprovalDate], 1, 0) +
IIF(#2026-02-16# > [ApplicationDate] AND #2026-02-16# <= [ApprovalDate], 1, 0) +
IIF(#2026-04-16# > [ApplicationDate] AND #2026-04-16# <= [ApprovalDate], 1, 0) +
IIF(#2026-05-25# > [ApplicationDate] AND #2026-05-25# <= [ApprovalDate], 1, 0) +
IIF(#2026-06-19# > [ApplicationDate] AND #2026-06-19# <= [ApprovalDate], 1, 0) +
IIF(#2026-07-03# > [ApplicationDate] AND #2026-07-03# <= [ApprovalDate], 1, 0) +
IIF(#2026-09-07# > [ApplicationDate] AND #2026-09-07# <= [ApprovalDate], 1, 0) +
IIF(#2026-10-12# > [ApplicationDate] AND #2026-10-12# <= [ApprovalDate], 1, 0)
```

### 3.6 `Holidays - Application to Issue`
In the Data pane, right-click 3.5 → **Duplicate**, then rename it. Edit the formula and replace every `[ApprovalDate]` with `[IssueDate]`, 13 places in all.

### 3.7 `Business Days to Approve` ⭐ primary metric
```
IF [In Scope (FY26 New Issued)] THEN
[Weekday Index - Approval] - [Weekday Index - Application] - [Holidays - Application to Approval]
END
```
> **Why the `IF` wrapper:** permits outside the scope return NULL, so the FIXED overall average in 3.16 is computed only over in-scope permits. FIXED calculations ignore ordinary worksheet filters.

### 3.8 `Business Days to Issue`
```
IF [In Scope (FY26 New Issued)] AND NOT ISNULL([ApprovalDate]) THEN
[Weekday Index - Issue] - [Weekday Index - Application] - [Holidays - Application to Issue]
END
```
> This uses the same 2,987 measured permits as the approval metric, so the two can be compared directly.

### 3.9 `QA Mismatch`
```
ABS([Business Days to Approve] - [BusinessDaysToApprove_QA])
```
> `BusinessDaysToApprove_QA` was calculated independently in Python, stepping through the calendar day by day. This field proves the Tableau logic matches it.

### 3.10 `Approval Time Band`
```
IF ISNULL([Business Days to Approve]) THEN NULL
ELSEIF [Business Days to Approve] = 0 THEN "Same day"
ELSEIF [Business Days to Approve] <= 5 THEN "1-5 days"
ELSEIF [Business Days to Approve] <= 10 THEN "6-10 days"
ELSEIF [Business Days to Approve] <= 20 THEN "11-20 days"
ELSEIF [Business Days to Approve] <= 40 THEN "21-40 days"
ELSEIF [Business Days to Approve] <= 60 THEN "41-60 days"
ELSE "61+ days" END
```

### 3.11 – 3.20 Aggregate measures

| # | Name | Formula | Default number format |
|---|---|---|---|
| 3.11 | `Avg Business Days to Approve` | `AVG([Business Days to Approve])` | Number, 1 decimal |
| 3.12 | `Median Business Days to Approve` | `MEDIAN([Business Days to Approve])` | Number, 0 decimals |
| 3.13 | `Avg Business Days to Issue` | `AVG([Business Days to Issue])` | Number, 1 decimal |
| 3.14 | `Permits (measured)` | `COUNTD(IF NOT ISNULL([Business Days to Approve]) THEN [TrackingNumber] END)` | Number, 0 decimals, thousands separator |
| 3.15 | `Permits In Scope` | `COUNTD(IF [In Scope (FY26 New Issued)] THEN [TrackingNumber] END)` | Number, 0 decimals, thousands separator |
| 3.16 | `Overall Avg (FIXED)` | `{ FIXED : AVG([Business Days to Approve]) }` | Number, 1 decimal |
| 3.17 | `Diff vs Overall` | `[Avg Business Days to Approve] - AVG([Overall Avg (FIXED)])` | Number, 1 decimal |
| 3.18 | `% Approved Within 10 Business Days` | `SUM(IIF([Business Days to Approve] <= 10, 1, 0)) / COUNT([Business Days to Approve])` | Percentage, 0 decimals |
| 3.19 | `QA Mismatch Total` | `SUM([QA Mismatch])` | Number, 0 decimals |
| 3.20 | `Speed vs Overall` | see below | (string) |

```
// 3.20 Speed vs Overall
IF [Diff vs Overall] <= -5 THEN "Faster than overall"
ELSEIF [Diff vs Overall] >= 5 THEN "Slower than overall"
ELSE "Near overall" END
```

**To set a default number format:** in the Data pane, right-click the field → **Default Properties → Number Format…**.

---

## 4. Scope filter

Every sheet must show only in-scope permits. **Add the filter once, as a data source filter:**

1. Go to the **Data Source** tab, then click **Filters → Add…** in the top-right corner.
2. Click **Add…**, choose **`In Scope (FY26 New Issued)`**, tick **True**, and click **OK** twice.

✅ **Check:** on a blank sheet, double-click `Permits In Scope`. It should show **2,992**.

> **Alternative:** drag `In Scope (FY26 New Issued)` to the Filters shelf of each worksheet and keep only **True**. The results are identical, because the business-day measures already return NULL outside the scope.

---

## 5. Worksheets

Rename each sheet by double-clicking its tab. Edit sheet titles by double-clicking the title on the sheet.

### Sheet 1 — `KPI - Overall` (requirement #1)
This is a labelled table of the headline measures.

1. Drag **Measure Names** (bottom of the Data pane) to **Rows**.
2. Drag **Measure Values** to **Text** on the Marks card. Set the mark type to **Text**.
3. The **Measure Values** card lists every measure. Drag off everything except the following, then drag them into this order:
   1. `AGG(Avg Business Days to Approve)`
   2. `AGG(Median Business Days to Approve)`
   3. `AGG(% Approved Within 10 Business Days)`
   4. `AGG(Avg Business Days to Issue)`
   5. `AGG(Permits (measured))`
   6. `AGG(Permits In Scope)`
   7. `AGG(QA Mismatch Total)`
4. Rename the row labels: right-click each Measure Names header in the view → **Edit Alias…**.

   | Measure | Alias |
   |---|---|
   | Avg Business Days to Approve | Average business days to approve |
   | Median Business Days to Approve | Median business days to approve |
   | % Approved Within 10 Business Days | % approved within 10 business days |
   | Avg Business Days to Issue | Avg business days to issue (incl. applicant payment) |
   | Permits (measured) | Permits measured |
   | Permits In Scope | Permits in scope |
   | QA Mismatch Total | QA mismatches vs. Python check (should be 0) |

5. Format:
   - Right-click the Measure Names header → **Hide Field Labels for Rows**.
   - **Format → Font**: Header 10pt dark grey, Pane 11pt bold navy (#1F3864).
6. Title: **Overall FY26 performance**.

✅ **Check:** 22.2 · 13 · 43% · 44.7 · 2,987 · 2,992 · **0**

### Sheet 2 — `Distribution`
1. Put `Approval Time Band` on **Columns** and `Permits (measured)` on **Rows**. Set the mark type to **Bar**.
2. Sort the bands in time order: click the `Approval Time Band` pill → **Sort…** → Sort By **Field**, Ascending, Field `Business Days to Approve`, Aggregation **Minimum**.
3. Drag `Permits (measured)` to **Label**. Click **Label** and tick *Show mark labels*.
4. Title: **How long approvals take: permits by approval-time band**

✅ **Check:**
| Band | Same day | 1-5 | 6-10 | 11-20 | 21-40 | 41-60 | 61+ |
|---|---|---|---|---|---|---|---|
| Permits | 664 | 405 | 206 | 631 | 549 | 253 | 279 |

The total is 2,987. 22% are approved the same day and 9% take more than 60 days.

### Sheet 3 — `By Permit Category` (requirement #2)
1. Put `PermitCategory` on **Rows** and `Avg Business Days to Approve` on **Columns**. Set the mark type to **Bar**.
2. Sort descending: hover over the axis and click the sort icon, or use the pill → **Sort** → By Field → `Avg Business Days to Approve`, Descending.
3. Drag `WorkTypeFamily` to **Color**. All Excavation subtypes then share one color, so the other families stand out.
4. **Label:** drag `Avg Business Days to Approve` and `Permits (measured)` to **Label**. Click **Label → Text "…"** and enter:
   ```
   <AGG(Avg Business Days to Approve)>  (n=<AGG(Permits (measured))>)
   ```
   Make the first field bold. Tick *Show mark labels*.
5. **Tooltip:** drag `Median Business Days to Approve`, `Avg Business Days to Issue` and `Diff vs Overall` to **Tooltip**.
6. **Overall-average reference line:**
   1. Drag `Overall Avg (FIXED)` to **Detail**. Right-click the pill → **Measure → Average**.
   2. Open the **Analytics** pane and drag **Reference Line** onto the view, dropping it on **Table**.
   3. Set Value to **AVG(Overall Avg (FIXED))**, Aggregation **Average**.
   4. Set Label to **Custom**: `Overall avg: <Value>`.
   5. Set Line to dashed, dark grey.
7. Title: **Average business days to approve, by permit category**

✅ **Check:**
| Category | Avg | n |
|---|---|---|
| Landscaping | 52.8 | 9 |
| Multiple Work Types | 51.0 | 111 |
| Paving | 39.4 | 46 |
| Excavation – Telecom | 37.0 | 35 |
| Excavation – Multiple Utilities | 36.3 | 95 |
| Projections | 35.9 | 9 |
| Excavation – Water | 35.7 | 951 |
| Fixture | 33.9 | 70 |
| Over Head Work | 27.9 | 62 |
| Excavation – Test Pit / Boring | 23.6 | 43 |
| Excavation – Other | 21.5 | 51 |
| Excavation – Electric | 21.0 | 147 |
| Excavation – Gas | 8.0 | 1,233 |
| Excavation – Sewer / Storm | 0.9 | 125 |

The reference line sits at **22.2**.

### Sheet 4 — `By Applicant Type` (requirement #3)
1. Duplicate Sheet 3: right-click its tab → **Duplicate**. Rename the copy.
2. Replace `PermitCategory` on Rows with **`ApplicantType`**. Sort descending by the average.
3. Replace `WorkTypeFamily` on Color with **`Speed vs Overall`**. Click **Color → Edit Colors…**:

   | Value | Color |
   |---|---|
   | Faster than overall | green (#59A14F) |
   | Near overall | grey (#BAB0AC) |
   | Slower than overall | orange (#F28E2B) |

4. The label, tooltip and reference line carry over from Sheet 3.
5. Title: **Average business days to approve, by applicant type**

✅ **Check:**
| Applicant | Avg | n |
|---|---|---|
| Private / Other | 44.1 | 246 |
| Government Agency | 38.7 | 23 |
| Utility – Telecom | 36.9 | 77 |
| Utility – DC Water | 31.2 | 1,132 |
| Utility – Pepco | 24.6 | 193 |
| Utility – Washington Gas | 8.9 | 1,316 |

### Sheet 5 — `Resubmission Impact`
1. Duplicate Sheet 3. Replace Rows with **`ResubmissionRequested`**.
2. Replace Color with **`ResubmissionRequested`**: No = blue, Yes = orange.
3. Sort ascending by the average.
4. Title: **Resubmission requested vs. not**

✅ **Check:** No **12.4** (n=2,171) · Yes **48.3** (n=816)

### Sheet 6 — `Work Location Size`
1. Duplicate Sheet 3. Replace Rows with **`LocationBucket`**. Remove `WorkTypeFamily` from Color.
2. Sort in size order: click the pill → **Sort** → By Field, Ascending, `NumBlockLocations`, **Minimum**.
3. Title: **By number of blocks on the permit**

✅ **Check:** 1 block **13.5** · 2-5 blocks 38.3 · 6-20 blocks **51.7** · 21+ blocks 45.7

### Sheet 7 — `Applicant x Resubmission` (cross-check)
1. Put `ApplicantType` on **Rows** and `ResubmissionRequested` on **Columns**. Set the mark type to **Square**.
2. Put `Avg Business Days to Approve` on **Color**. Click **Color → Edit Colors** → choose a sequential palette, such as Orange.
3. Put `Avg Business Days to Approve` and `Permits (measured)` on **Label**. Edit the label to:
   ```
   <AGG(Avg Business Days to Approve)>
   n=<AGG(Permits (measured))>
   ```
4. Title: **Avg business days: applicant type x resubmission (gap holds in every row)**

✅ **Check:**
| Applicant | No | Yes |
|---|---|---|
| Washington Gas | 5.5 | 33.6 |
| DC Water | 19.6 | 54.9 |
| Private / Other | 20.3 | 55.2 |
| Pepco | 18.0 | 33.2 |

### Sheet 8 — `Approval vs Issuance`
1. Put `PermitCategory` on **Rows**.
2. Put `Avg Business Days to Approve` on **Columns**, then drag `Avg Business Days to Issue` next to it on **Columns**. You get two side-by-side bar panels.
3. Set the mark type to **Bar** on the *All* Marks card. Tick *Show mark labels*. Drag `Permits (measured)` to **Tooltip**.
4. Sort descending by `Avg Business Days to Approve`.
5. Title: **Business days to approve (DDOT) vs. to issue (incl. applicant payment)**

✅ **Check:** Gas shows **8.0** to approve and **55.3** to issue. Overall, issuance adds about 22.5 business days after approval (median 3).

### Sheet 9 — `By Ward`
1. Put `Ward` on **Columns** and `Avg Business Days to Approve` on **Rows**. Set the mark type to **Bar**.
2. Put `Avg Business Days to Approve` on **Label**, plus `Permits (measured)`, `Median…` and `Avg…to Issue` on **Tooltip**.
3. Title: **Average business days to approve, by ward (little variation)**

✅ **Check:** values range from **18.2** (Ward 6) to **27.2** (Ward 3).

### Sheet 10 — `Monthly Trend (censored)`
1. Drag `ApplicationDate` to **Columns**. Right-click the pill and choose the **second** "Month" option, the *continuous* one (for example "May 2015").
2. Put `Avg Business Days to Approve` on **Rows**. Set the mark type to **Line**. Put the average on **Label** and `Permits (measured)` on **Tooltip**.
3. Edit the title to two lines. Make the second line 9pt red:
   ```
   By application month
   CAUTION: late-FY months only include permits issued by 9/30/2026, so they are biased toward fast approvals.
   ```

✅ **Check:** about 60 days in Feb–Mar 2026, falling to about 5 in Aug–Sep 2026. That drop comes from the year-end cut-off, not a real improvement (see REPORT_SUMMARY Insight 9).

---

## 6. Dashboards

### 6.1 Dashboard 1 — `FY26 Permit Approval Times`

**Setup:**
1. Click **New Dashboard** (bottom tab bar) and rename it **FY26 Permit Approval Times**.
2. Size: **Fixed size → Custom, 1400 × 1000**.
3. From **Objects**, drag a **Vertical** container onto the canvas. Everything below goes inside it, top to bottom.

**Layout:**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ① Title (Text)                                                          ~5%   │
│ ② Subtitle (Text)                                                       ~5%   │
├───────────────────────────┬───────────────────────────────────────────────────┤
│ ③ "1 | Overall performance"│ ⑥ "2 | By permit type category"                 │
│ ④ KPI - Overall  (~21%)   │ ⑦ By Permit Category                     ~40%    │
│ ⑤ Distribution   (~15%)   │                                                   │
├───────────────────────────┴───────────────────────────────────────────────────┤
│ ⑧ "3 | Where approval times differ"                                     ~4%   │
├──────────────────────────┬──────────────────────────┬─────────────────────────┤
│ ⑨ By Applicant Type      │ ⑩ Resubmission Impact     │ ⑪ Work Location Size   │ ~31%
├──────────────────────────┴───────────────┬──────────┴─────────────────────────┤
│ ⑫ Key takeaways (Text)                   │ ⑬ Next steps (Text)                │ ~15%
└──────────────────────────────────────────┴────────────────────────────────────┘
   left column ≈ 32% width / right ≈ 68%;  row 3 split ≈ 34 / 33 / 33;  row 4 ≈ 62 / 38
```

**Steps:**

1. **① Title:** drag a **Text** object in. Type:
   > FY2026 Public Space Construction Permits: Business Days to Approve

   Format it 20pt, bold, navy (#1F3864).
2. **② Subtitle:** add a **Text** object, 10pt dark grey:
   > New permits applied for on or after Oct 1, 2025 and issued in FY26 (Oct 1, 2025 - Sep 30, 2026). Business days count from application to DDOT's final approval and exclude weekends and DC holidays. Source: DDOT TOPS, deduplicated to one row per permit. Click a permit category to filter the whole dashboard; click again to clear.
3. **Row 2:** drag a **Horizontal** container below the subtitle. Inside it, place two **Vertical** containers side by side.
   - **Left container:**
     - ③ a Text object, **"1 | Overall performance"**, 12pt bold navy, background **#DCE6F2** (Layout pane → Background)
     - ④ the **KPI - Overall** sheet. Right-click it → untick **Title**.
     - ⑤ the **Distribution** sheet
   - **Right container:**
     - ⑥ a Text object: **"2 | By permit type category"**, followed in 9pt grey by *"Click a bar to filter the dashboard; line = overall average; Excavation is split by utility because it is 90% of permits"*. Same background.
     - ⑦ the **By Permit Category** sheet
   - Drag the divider so the left column is about one-third of the width.
4. **⑧ Section header:** below row 2, add a Text object: **"3 | Where approval times differ"**, then in 9pt grey: *"Resubmission and project size separate fast from slow; geography does not (see Data Segmentation tab)"*. Background **#DCE6F2**.
5. **Row 3:** add a **Horizontal** container with ⑨ **By Applicant Type**, ⑩ **Resubmission Impact** and ⑪ **Work Location Size**. Select the container → **Distribute Contents Evenly**.
6. **Row 4:** add a **Horizontal** container with two Text objects, both with background **#F2F2F2**.
   - **⑫ Key takeaways** (heading 12pt bold navy, body 10pt):
     > - 22.2 avg / 13 median business days. The average blends a same-day group (22%) with a 60+ day tail (9%).
     > - Widest gap is resubmission: 12.4 vs 48.3 days. 27% of permits account for 59% of approval days.
     > - Project size: 1 block 13.5 days vs 6-20 blocks 51.7. DC Water single-block permits take 7 days, multi-block 41-52.
     > - Category: Sewer/Storm 0.9 and Gas 8.0, up to Water 35.7 and Multiple Work Types 51.0. Water is 32% of permits and 51% of approval days.
     > - Applicant: Washington Gas 8.9, DC Water 31.2, Private 44.1. Private applicants are asked to resubmit 68% of the time.
   - **⑬ Next steps:**
     > 1. Analyze reasons for Revise & Resubmit requests by category.
     > 2. Review DC Water multi-block lateral work as a program.
     > 3. Split time into queue, review, and applicant-payment stages.
     > 4. Use cohort-based trends (the monthly view is cut off at year end).
     >
     > *Holidays excluded: 10/13, 11/11, 11/27, 12/25, 1/1, 1/19, 2/16, 4/16, 5/25, 6/19, 7/3, 9/7* (9pt grey)
7. **Legends:** keep the `WorkTypeFamily` color legend next to the category chart. Remove any other legends Tableau adds, using the **×** on each legend.

**Filter action (click a category to filter):**
1. Go to **Dashboard → Actions… → Add Action → Filter…**.
2. Name: **Filter by Permit Category**.
3. Source Sheets: dashboard *FY26 Permit Approval Times*, tick only **By Permit Category**. Run action on: **Select**.
4. Target Sheets: the same dashboard. Tick every sheet **except** By Permit Category.
5. Clearing the selection will: **Show all values**. Click **OK**.

✅ **Check:**
- Click **Excavation - Water**. The KPI changes to about **35.7**, and Work Location Size shows the jump from 1 block to multi-block.
- The reference lines stay at **22.2**, because they're FIXED, so each filtered group is still compared with the all-permit average.
- Click the bar again to clear the filter.

### 6.2 Dashboard 2 — `Data Segmentation`

1. Create a new dashboard named **Data Segmentation**, sized **1400 × 1000**, with a **Vertical** container.
2. Title Text, 20pt bold navy:
   > Data segmentation: what separates fast and slow approvals

   Add a second line in 10pt grey:
   > Cross-checks behind the main dashboard: is the gap real within each group, and where does time go after approval?
3. Add a **Horizontal** container with **Applicant x Resubmission** and **Approval vs Issuance**.
4. Add another **Horizontal** container with **By Ward** and **Monthly Trend (censored)**.
5. Distribute the contents of each row evenly.
6. Below the two rows, add a Text object for **Key takeaways** (12pt bold navy heading, 10pt grey bullets, background **#F2F2F2**), sized to about 20% of the height:
   - Resubmission gap holds for every applicant type: Washington Gas 5.5 vs 33.6 days, DC Water 19.6 vs 54.9, Private 20.3 vs 55.2. It is not an applicant-mix effect.
   - Most permits issue 3-5 business days after approval. Excavation - Gas is the exception: 8.0 days to approve but 55.3 to issue, and it holds 87% of all post-approval days.
   - The gas issuance wait is skewed (median 6 days, but 36% wait 20+), so it points to a payment or pickup step on a subset of permits, not to DDOT review.
   - Geography explains little: Wards 1-8 average 18.2 to 27.2 days with medians of 9 to 17. Only the 18 multi-ward permits stand out (36.8).
   - The monthly drop is not an improvement: Oct-May applications average 37.6 days vs 12.4 for Jun-Sep, because slow late-year permits were not yet issued by 9/30.
   - Where to act: Revise & Resubmit requests and the gas approval-to-issuance gap, not ward-level or seasonal factors.

---

## 7. Final checks and packaging

### 7.1 QA checklist
- [ ] Data source filter `In Scope (FY26 New Issued)` = True. `Permits In Scope` shows **2,992**.
- [ ] KPI shows **22.2** avg, **13** median, **43%** within 10 days, **44.7** to issue, **2,987** measured.
- [ ] **QA mismatches = 0**. The Tableau business-day logic matches the independent Python calculation for every permit.
- [ ] By Permit Category: Sewer/Storm 0.9 is lowest and Landscaping 52.8 is highest. The reference line is at 22.2.
- [ ] Applicant, Resubmission and Location sheets match the ✅ values above.
- [ ] The filter action works and clears correctly.
- [ ] No text is cut off at 1400 × 1000. Check with **Dashboard → Device Preview** if needed.

### 7.2 Create an extract and package the workbook
1. Go to the **Data Source** tab and set Connection to **Extract**. Click any sheet tab, and save the `.hyper` file when prompted.
2. **File → Save As…**, type **Tableau Packaged Workbook (*.twbx)**, name **`FY26_Public_Space_Permit_Approvals.twbx`**.
   A `.twbx` embeds the extract, so reviewers can open it without the CSV.
3. Optional: use **File → Export As PowerPoint…** or **Print to PDF** for a static copy of each dashboard.

### 7.3 Zip for submission
Put these files in one folder named `Fulton_Q_Shannon_Tableau`:
- the `.twbx`
- `README.md`
- `REPORT_SUMMARY.md`
- `Tableau_Build_Guide.md`
- `scripts/01_pull_permits.py` and `scripts/02_prepare_permits.py`
- `data/permits_by_tracking_number.csv` and `data/dc_holidays.csv`

Then right-click the folder → **Send to → Compressed (zipped) folder**, and name the zip **`Fulton_Q_Shannon_Tableau.zip`**.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| A date column shows as "Abc" (string) | Data Source page → click the type icon → **Date** |
| Business-day values are NULL for everything | `In Scope` isn't True for any row. Check that `NewOrRenewal` contains "New" and the dates are typed as Date. |
| `QA Mismatch Total` is not 0 | A holiday date was mistyped in 3.5 or 3.6. Compare against the holiday table in §1. |
| The reference line isn't at 22.2 | The line's value must be `AVG(Overall Avg (FIXED))`, not the bar measure itself. |
| `Permits In Scope` is not 2,992 | `TrackingNumber` was read as a number. Change it to String (§2). |
| The filter action also filters the category chart | In Target Sheets, untick By Permit Category |
