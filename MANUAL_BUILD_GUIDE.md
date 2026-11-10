# Building the FY26 Permit Approval Workbook by Hand in Tableau Desktop

This guide rebuilds `DDOT_FY26_Permit_Approval_Times.twbx` by hand in Tableau Desktop.

- **Result:** 11 worksheets, 2 data sources and 1 dashboard.
- **Time needed:** about 60–90 minutes.
- **Section 10** lists the numbers each sheet should show, so you can check your work.

> **Tableau version.** Tableau Desktop 2023.1 or later is recommended. Tableau Public Desktop also works for every step, but it can only save to your Tableau Public profile, not to a local `.twbx` file. The submission needs a packaged `.twbx`, so use Tableau Desktop (the 14-day trial is fine) for the final save.

---

## 0. Before you start

1. Make sure the cleaned data file exists:
   `X:\tableau-cs12-Data-scientist\data\fy26_new_issued_permits.csv` (11,206 rows).
   To rebuild it from the live feed:
   ```
   cd X:\tableau-cs12-Data-scientist
   .venv\Scripts\python scripts\pull_permits.py
   .venv\Scripts\python scripts\prepare_permits.py
   ```
   > The feed changes over time, so a fresh pull may give slightly different numbers than section 10.
2. All the filtering and the business-day math are already done in Python, so Tableau needs **no filters**. The CSV contains only:
   - new permits (no renewals),
   - applied for on or after Oct 1, 2025,
   - issued between Oct 1, 2025 and Sep 30, 2026,

   and its business-day columns already exclude weekends and DC holidays.
3. Fields you'll use most:

| CSV field | Meaning |
|---|---|
| `BusDaysToApprove` | Business days from application to final approval (0 = same day; empty for the 13 permits with no approval date) |
| `BusDaysToIssue` | Business days from application to issuance |
| `BusDaysApproveToIssue` | Business days from final approval to issuance (payment / pick-up stage) |
| `WorkFocus` | **Permit type category**, built from each permit's line items |
| `PermitCategory` | Broad work type from the TOPS `Is*` flags (97% are Excavation) |
| `ApplicantGroup` | DC Water (Lead Free DC), DC Water (Other), Washington Gas, Pepco, Telecom, Government, Private, Not Recorded |
| `LeadFreeDC` | "Lead Free DC program" or "All other permits" |
| `ApprovalBucket` | Approval time band ("01) Same day" … "07) Over 60 days"). The number prefix keeps the bands in order. |
| `SameDayApproval` | 1 if approved the same day it was submitted, else 0 |
| `ApplicationMonth`, `IssueMonth` | First day of the month |
| `Ward`, `Quadrant`, `NeighborhoodNames` | Location |

---

## 1. Connect to the data

1. Open Tableau Desktop. Under **Connect → To a File**, click **Text file**.
2. Browse to `fy26_new_issued_permits.csv` and click **Open**. The **Data Source** page opens with the file as the only table.
3. Rename the data source: double-click the name in the top-left corner and enter `FY26 New Issued Permits`.
4. Leave the connection type as **Live**. Making an extract is optional; the packaged workbook includes the CSV either way.
5. In the data grid, check the data type icon above each column. Click an icon to change it.

| Field | Should be |
|---|---|
| `ApplicationDate`, `AssignedDate`, `LastApprovalDate`, `IssueDate`, `EffectiveDate`, `ExpirationDate` | Date & Time |
| `ApplicationMonth`, `IssueMonth` | Date |
| `BusDays…`, `DaysTo…`, `LineItemCount`, `SameDayApproval` | Number (whole) |
| `TotalFee`, `PermitFee`, `Latitude`, `Longitude` | Number (decimal) |
| `WorkLocationZip` | **String**. Tableau may guess Number; change it. |
| Everything else | String |

6. Click **Sheet 1** at the bottom to go to the first worksheet.

---

## 2. Tidy up the fields (Data pane)

**Make the ID fields dimensions.** In the Data pane, drag `OBJECTID` and `TrackingNumber` from **Measures** up into **Dimensions**, or right-click each one and choose **Convert to Dimension**. They are IDs and should never be summed.

**Rename fields.** Right-click a field, choose **Rename**, and enter the new name:

| Field | Rename to |
|---|---|
| `BusDaysToApprove` | Business Days to Approve |
| `BusDaysToIssue` | Business Days to Issue |
| `BusDaysApproveToIssue` | Business Days Approval to Issue |
| `BusDaysToAssign` | Business Days to Assign |
| `WorkFocus` | Permit Type Category |
| `PermitCategory` | Work Type (TOPS flags) |
| `ApplicantGroup` | Applicant Group |
| `LeadFreeDC` | Lead Free DC Program |
| `ApprovalBucket` | Approval Time Band |
| `ApplicationMonth` | Application Month |
| `ReviewedByPublicSpaceCommittee` | Public Space Committee Review |

**Optional: clean up the band labels.**
1. Right-click **Approval Time Band** and choose **Aliases…**.
2. Give each band a label without its number prefix. For example, `01) Same day` becomes `Same day`, and `07) Over 60 days` becomes `Over 60 days`.

Aliases change only what is displayed; the bands still sort in the right order.

**Optional: assign colours to the Lead Free DC field.**
1. Right-click **Lead Free DC Program** and choose **Default Properties → Color…**.
2. Set "Lead Free DC program" to orange (`#F28E2B`) and "All other permits" to blue (`#4E79A7`).
3. Click **OK**.

The colours then stay the same on every sheet.

---

## 3. Create the calculated fields

Create each field as follows:
1. In the Data pane, open the ▾ menu and choose **Create Calculated Field…**.
2. Type the name, paste the formula, and click **OK**.
3. To set the number format, right-click the new field and choose **Default Properties → Number Format…**.

| Name | Formula | Number format |
|---|---|---|
| Avg Business Days to Approve | `AVG([Business Days to Approve])` | Number (Custom), 1 decimal |
| Median Business Days to Approve | `MEDIAN([Business Days to Approve])` | Number (Custom), 1 decimal |
| Avg Business Days to Issue | `AVG([Business Days to Issue])` | Number (Custom), 1 decimal |
| Avg Business Days Approval to Issue | `AVG([Business Days Approval to Issue])` | Number (Custom), 1 decimal |
| Permits | `COUNTD([OBJECTID])` | Number (Custom), 0 decimals, thousands separator |
| % Approved Same Day | `AVG([SameDayApproval])` | Percentage, 1 decimal |
| % Over 60 Business Days | `SUM(IIF([Business Days to Approve] > 60, 1, 0)) / COUNT([Business Days to Approve])` | Percentage, 1 decimal |
| % of Permits | `[Permits] / TOTAL([Permits])` | Percentage, 1 decimal |

**Notes on the formulas:**
- If you didn't rename the fields in step 2, use the original names in the formulas, for example `[BusDaysToApprove]` instead of `[Business Days to Approve]`.
- These are aggregate calculations. They show as `AGG(...)` on shelves, and Tableau won't let you change their aggregation. That is expected.
- `COUNT([Business Days to Approve])` skips empty values. That keeps the 13 permits with no approval date out of the "over 60" percentage.

---

## 4. Worksheet 1: Overall Avg Business Days (headline numbers)

1. Rename **Sheet 1** to `1. Overall Avg Business Days` (double-click the tab).
2. Drag these fields onto **Text** on the Marks card: **Avg Business Days to Approve**, **Median Business Days to Approve**, **Permits**, **% Approved Same Day**, **% Over 60 Business Days** and **Avg Business Days to Issue**.
3. Set the mark type on the Marks card to **Text**.
4. Click **Text**, then the **…** button, and replace the contents with the layout below. Use **Insert ▸** to add each field.
   ```
   Average business days to approve
   <AGG(Avg Business Days to Approve)>
   Median <AGG(Median Business Days to Approve)>   |   Permits <AGG(Permits)>
   Same-day approvals <AGG(% Approved Same Day)>   |   Over 60 days <AGG(% Over 60 Business Days)>
   Avg business days application to issuance <AGG(Avg Business Days to Issue)>
   ```
5. Format the text:
   - First line: 11 pt grey.
   - The average: **36 pt, bold, blue (#4E79A7)**.
   - Remaining lines: 10 pt, with the values bold.
   - Alignment: centre.
6. Set the title. Double-click the title, or choose **Worksheet → Show Title** first, and enter:
   *FY26 average business days to approve (new permits issued in FY26)*.
7. In the toolbar, set **Fit** to **Entire View**.

✅ The big number should read **43.8**.

---

## 5. Worksheet 2: Avg Days by Permit Type

1. Create a new worksheet (the icon next to the sheet tabs) and name it `2. Avg Days by Permit Type`.
2. Build the chart:
   - **Permit Type Category** → **Rows**.
   - **Avg Business Days to Approve** → **Columns**. Tableau draws horizontal bars.
3. Sort: click the sort-descending button in the toolbar, or right-click **Permit Type Category** and choose **Sort → Field → Descending → Avg Business Days to Approve**.
4. Add labels: drag **Avg Business Days to Approve** onto **Label**.
5. Add to **Tooltip**: **Permits**, **Median Business Days to Approve**, **Avg Business Days to Issue** and **% Over 60 Business Days**.
6. Colour: click **Color** and choose blue `#4E79A7`.
7. Title: *Average business days to approve by permit type category*.
8. Optional reference line:
   1. Open the **Analytics** pane.
   2. Drag **Reference Line** onto **Table**.
   3. Choose Value: **Avg Business Days to Approve**, Aggregation: **Average**, Label: **Custom** "FY26 avg <Value>".

   This shows which categories are above or below the overall average.

✅ The top bars should be Other Excavation (57.8), Fixture (50.0) and Lead Service Line Replacement (48.3). Gas Utility Work is lowest at about 10.0.

> **Optional extra sheet:** duplicate this sheet and swap in **Work Type (TOPS flags)**. It shows why the flags alone are not a useful category: 97% of permits are Excavation.

---

## 6. Worksheet 3: Lead Free DC vs All Other

1. Create a new sheet named `3. Lead Free DC vs All Other`.
2. **Lead Free DC Program** → **Rows**; **Avg Business Days to Approve** → **Columns**.
3. Drag **Lead Free DC Program** onto **Color** as well.
4. Drag **Avg Business Days to Approve** onto **Label**.
5. Optional: drag **Permits** onto **Label** too, so each bar reads, for example, "48.4 | 9,429".
6. Add the same tooltip fields as on Sheet 2.
7. Sort descending by the average.
8. Title: *DC Water Lead Free DC permits vs. all other permits*.

✅ Lead Free DC program **48.4** (9,429 permits); All other permits **19.5** (1,777).

---

## 7. Worksheet 4: Avg Days by Applicant

1. Create a new sheet named `4. Avg Days by Applicant`.
2. **Applicant Group** → **Rows**; **Avg Business Days to Approve** → **Columns**.
3. Sort descending.
4. Add the average to **Label**, and the standard tooltip fields.
5. Title: *Average business days to approve by applicant group*.

✅ Highest is Not Recorded (52.0), then Private / Other (50.2) and DC Water (Lead Free DC) (48.4). Lowest is DC Water (Other) at 5.2.

---

## 8. Worksheet 5: Approval Time Distribution

1. Create a new sheet named `5. Approval Time Distribution`.
2. **Approval Time Band** → **Columns**; **Permits** → **Rows**.
3. Remove the "Not Approved" band (13 permits): right-click it in the view and choose **Exclude**.
4. Check the band order: it should run from Same day to Over 60. The number prefixes make an ascending alphabetical sort correct, so if needed choose **Sort → Alphabetic → Ascending**.
5. Drag **Lead Free DC Program** onto **Color**. The bars become stacked.
6. Drag **Permits** onto **Label**.
7. Tooltip: add **% of Permits** and **Avg Business Days to Approve**.
   - **% of Permits** uses `TOTAL()`, which here is computed per band (Table Down). For the share of all permits instead:
     1. Right-click the field on Tooltip.
     2. Choose **Compute Using → Table (across then down)**.
8. Title: *How many permits fall in each approval-time band (business days)*.

✅ The 21–40 band is the largest at 3,830 permits. Both 41–60 and Over 60 are about 2,640.

---

## 9. Worksheets 6, 7 and 8

### 6. Trend by Application Month
1. Create a new sheet named `6. Trend by Application Month`.
2. Drag **Application Month** to **Columns**.
3. Right-click the pill and choose the **second "Month"** option, the green continuous one that shows e.g. *May 2015*.
4. Drag **Avg Business Days to Approve** to **Rows**. The mark becomes a **Line**.
5. Drag **Lead Free DC Program** onto **Color**. This gives two lines.
6. Click **Label**, then **Show mark labels**, then choose **Min/Max** or **Line Ends** to keep the chart readable.
7. Tooltip: add **Permits**.
8. Title: *Average business days to approve by month of application*.
9. Add a caption (**Worksheet → Show Caption**) with this text:

   *Later months are lower partly because only permits issued by Sep 30, 2026 are included; slow late-year applications are still open.*

✅ Overall values by month: Jan 2026 is highest at 110.4. Aug 2026 is 6.7 and Sep 2026 is 4.4.

### 7. Avg Days by Ward
1. Create a new sheet named `7. Avg Days by Ward`.
2. **Ward** → **Columns**; **Avg Business Days to Approve** → **Rows**. Wards sort Ward 1–8 alphabetically.
3. Add the average to **Label**, and the standard tooltip fields.
4. Title: *Average business days to approve by ward*.

✅ Ward 3 is 60.1 (slowest); Ward 8 is 28.4 (fastest).

> **Optional map version:**
> 1. Double-click **Latitude**, then **Longitude**.
> 2. Drag **OBJECTID** to **Detail**.
> 3. Drag **Business Days to Approve** (as a dimension or as Avg) to **Color**.
> 4. Set the mark type to Circle with size about 20% and transparency 50%.

### 8. Approval vs Issuance by Applicant
This sheet splits total time into DDOT's approval stage and the stage after approval, which is driven by the applicant (payment and pick-up).

1. Create a new sheet named `8. Approval vs Issuance by Applicant`.
2. Drag **Applicant Group** to **Rows**.
3. Drag **Measure Values** to **Columns**.
4. On the **Measure Values** card that appears, remove every measure except:
   - **Avg Business Days to Approve**
   - **Avg Business Days Approval to Issue**

   To remove one, drag it off the card. Alternatively, use the **Measure Names** filter and keep only these two.
5. Drag **Measure Names** onto **Color**. The bars become stacked, approval stage plus issuance stage.
6. Set the colours: approval in blue `#4E79A7`, approval-to-issue in grey `#BAB0AC`.
7. Drag **Measure Values** onto **Label**.
8. Sort **Applicant Group** descending by **Avg Business Days to Issue**: right-click the field, choose **Sort → Field**, and pick Avg Business Days to Issue.
9. Title: *Where the time goes: approval stage vs. approval-to-issuance stage (avg business days)*.

✅ Washington Gas: about 11.5 days to approval plus about 45.0 days from approval to issue. Every other group's second stage is under 6 days.

> The two stages don't add up exactly to Avg Business Days to Issue. That's because averages taken over slightly different permit counts don't add up exactly, and because a few permits are issued on the same day they were approved.

### 9. Segments vs FY26 Average (purpose-built data source)
1. **Add the data source.**
   1. Choose **Data → New Data Source → Text file** and pick `data/segment_comparison.csv`.
   2. Name it `Segment Comparison vs FY26 Average`.
   3. Each row is one segment (for example *Ward: Ward 3*) with these columns:
      - `Permits`
      - `AvgBusDaysToApprove`
      - `ScopeAverage`
      - `DiffFromAverage`
      - `Flag` (*Meaningfully slower* / *Meaningfully faster* / *Within 7 days of average*)
      - `Scope` (*All FY26 permits* or *Excluding Lead Free DC*)
2. Create a new sheet named `9. Segments vs FY26 Average`.
3. Build the chart:
   - **SegmentLabel** → **Rows**.
   - **DiffFromAverage** (SUM) → **Columns**.
4. Add filters:
   - **Scope** → Filters, keep only *All FY26 permits*.
   - **Flag** → Filters, exclude *Within 7 days of average*.
5. Colour:
   1. Drag **Flag** onto **Color**.
   2. Click **Color → Edit Colors…** and set *Meaningfully slower* to orange `#F28E2B` and *Meaningfully faster* to blue `#4E79A7`.
6. Labels: drag **DiffFromAverage** onto **Label**. Set its number format to Custom `+#,##0.0;-#,##0.0`.
7. Tooltip: add **Permits**, **AvgBusDaysToApprove**, **MedianBusDaysToApprove** and **ScopeAverage**.
8. Sort **SegmentLabel** descending by SUM(DiffFromAverage).
9. Widen the row header (drag its edge) so the labels aren't cut off.
10. Title: *Segments 7+ business days from the FY26 average (43.8)*.

✅ Top bars: Public Space Committee Review: Yes **+28.1**, then FY26 Q1 **+27.3** and FY26 Q2 **+25.1**. Bottom bar: DC Water (Other) **-38.7**.

### 10. Segments excl. Lead Free DC
1. Duplicate sheet 9: right-click its tab and choose **Duplicate**.
2. Rename the copy `10. Segments excl. Lead Free DC`.
3. Change the **Scope** filter to *Excluding Lead Free DC*.
4. Title: *Excluding Lead Free DC: segments 7+ days from that average (19.5)*.

✅ Top bars: FY26 Q2 **+55.5**, committee review **+52.5**, other excavation **+38.3**.

### 11. Ward x Program Heatmap
1. Create a new sheet named `11. Ward x Program Heatmap` on the main data source.
2. **Ward** → **Rows**; **Lead Free DC Program** → **Columns**.
3. Set the mark type to **Square**.
4. Drag **Avg Business Days to Approve** onto **Color** and onto **Label**.
5. Tooltip: add **Permits** and **Median Business Days to Approve**.
6. Title: *Avg business days by ward and program*.

✅ Lead Free DC column: Ward 3 **68.9**, Ward 8 **30.2**. All other permits: every ward between **15.4 and 23.6**.

---

## 10. Check the numbers before building the dashboard

| Check | Expected |
|---|---|
| Permits (all) | 11,206 |
| Avg business days to approve | 43.8 |
| Median | 39.0 |
| % approved same day | 3.3% |
| % over 60 business days | 23.6% |
| Avg business days to issue | 52.3 |
| Lead Free DC / All other | 48.4 / 19.5 |
| Lead Service Line / Gas / Water-Sewer / Electric-Telecom | 48.3 / 10.0 / 19.1 / 25.2 |
| Fixture / Paving / Overhead / Mega Project / Other Excavation | 50.0 / 35.5 / 30.0 / 17.7 / 57.8 |
| Washington Gas approve / approve-to-issue | 11.5 / 45.0 |
| Public Space Committee review = Yes | 61 permits, 72.0 days |
| Ward 3 / Ward 8 | 60.1 / 28.4 |

**If a number doesn't match:**
- Check that the field types are correct (section 1, step 5).
- Check that no stray filter is on the Filters shelf.
- Check that `OBJECTID` was counted with COUNTD, not summed.

---

## 11. Build the dashboard

### 11.1 Set up the dashboard
1. Click **New Dashboard** (the icon next to the sheet tabs) and name it `FY26 Permit Approval Dashboard`.
2. In the **Size** dropdown on the left, choose **Range**:
   - width: minimum **1200**, maximum **1600**;
   - height: minimum and maximum both **1760**.

   This fits laptop screens without horizontal scrolling.
3. Optional: under **Dashboard → Format**, set the background to white and the default title font to Tableau Book.

### 11.2 Layout plan
Build it from top to bottom inside one **Vertical** container:

```
┌───────────────────────────────────────────────────────────────┐
│ TITLE (Text)                                          ~7%     │
│ HOW TO READ THIS (Text)                               ~5%     │
├───────────────────────────────────────────────────────────────┤
│ Section 1 header (Text)                                       │
│ [1. Overall KPI 34%] [5. Approval Time Distribution 66%] ~22% │
├───────────────────────────────────────────────────────────────┤
│ Section 2 header (Text)                                       │
│ [2. By Permit Type 50%]     [3. Lead Free DC vs Other 50%]    │
├───────────────────────────────────────────────────────────────┤
│ Section 3 header (Text)                                       │
│ [4. Applicant] [6. Month Trend] [8. Approval vs Issuance]     │
├───────────────────────────────────────────────────────────────┤
│ Section 4 header (Text)                                       │
│ [9. Segments 37%] [10. Segments excl. LFDC 37%] [11. Heatmap] │
├───────────────────────────────────────────────────────────────┤
│ KEY INSIGHTS AND NEXT STEPS (Text)                    ~9%     │
└───────────────────────────────────────────────────────────────┘
```

### 11.3 Steps
1. From **Objects**, drag a **Vertical** container onto the canvas so it fills the whole dashboard.
2. **Title.** Drag a **Text** object into the top of the container and enter:
   - **Public Space Construction Permits: FY26 Average Business Days to Approve** in 20 pt, bold, dark blue `#1F3B57`.
   - On a new line: *DDOT Public Space Division | Analytics, Assets, and Performance Branch | Source: DC GIS TOPS feed (MapServer/23), pulled Nov 2026* in 9 pt grey.
3. **How to read this.** Drag a **Text** object just below the title and enter, in 9 pt:

   **How to read this:** Scope is new permits (no renewals) applied for on or after Oct 1, 2025 and issued in FY26 (Oct 1, 2025 – Sep 30, 2026): 11,206 permits. Business days = days from application to final approval, excluding weekends and DC holidays (same-day approval = 0). Hover any mark for permit counts, median and days to issuance.
4. **Section 1.**
   1. Add a **Text** object with **1. Overall performance** (13 pt bold) and, on a new line, *The FY26 average, and how widely approval times are spread around it.* (9 pt grey).
   2. Drag a **Horizontal** container below it.
   3. Drag sheet **1. Overall Avg Business Days** into the horizontal container, then **5. Approval Time Distribution** to its right.
   4. Drag the divider so the KPI sheet takes about a third of the width.
5. **Section 2.**
   1. Add a **Text** header: **2. Approval time by permit type category**, with the note *Permit type is derived from the line items on each permit. Lead service line replacements (DC Water's Lead Free DC program) are 84% of permits and drive the overall average.*
   2. Add a **Horizontal** container below it.
   3. Put **2. Avg Days by Permit Type** and **3. Lead Free DC vs All Other** in it, at 50% width each.
6. **Section 3.**
   1. Add a **Text** header: **3. Other segments worth exploring**, with the note *Applicant, timing and stage of the process show where approval times are meaningfully different.*
   2. Add a **Horizontal** container below it.
   3. Put **4. Avg Days by Applicant**, **6. Trend by Application Month** and **8. Approval vs Issuance by Applicant** in it.
   4. Distribute them evenly: select the container, then **▾ → Distribute Contents Evenly**.
7. **Section 4.**
   1. Add a **Text** header: **4. Where approval times are meaningfully different**, with the note *Segments with 30+ permits whose average is 7+ business days above (orange) or below (blue) the average. The middle chart removes Lead Free DC so program mix doesn't drive the result.*
   2. Add a **Horizontal** container below it.
   3. Put sheets **9**, **10** and **11** in it, at about 37% / 37% / 26% width.

   > **Tip:** to make a row a fixed height, select its container and choose **▾ → Edit Height…**. Fixed heights stop Tableau from shrinking one section to make room for another.
8. **Key insights.** Drag a **Text** object to the bottom and enter:

   **Key insights and next steps**
   - Overall: 43.8 business days on average (median 39); only 3% are approved the same day and 24% take more than 60 business days.
   - Lead Free DC permits average 48.4 days vs. 19.5 for all other permits — most of the FY26 backlog is one program. Gas (10.0), water/sewer (19.1) and electric/telecom (25.2) utility work is approved much faster.
   - Washington Gas is approved in 11.5 days but waits 45 more days on average between approval and issuance (payment / pick-up), so its total time is similar to other groups.
   - Applications from Oct 2025 – Mar 2026 took 65–110 days. Later months look faster partly because only permits issued by Sep 30 are included. Ward 3 is slowest (60.1) and Ward 8 fastest (28.4) — worth exploring next.
9. **Tidy up.**
   - Drag the section dividers until the heights roughly match the layout plan.
   - Hide the colour legend that Tableau adds automatically for **Lead Free DC Program**, or move it under Section 2 (select it, then **▾ → Floating**, or drag it into place).
   - Hide the **Measure Names** legend for sheet 8, or keep it next to that chart; it explains blue vs grey.
   - Select each sheet and make sure **Fit** is **Entire View** (or **Fit Width** for the bar charts).
   - Optional: under **Layout → Border**, give each section a light grey border, and add 8 px of **Outer Padding** so the sections read as blocks.

### 11.4 Optional interactivity
- **Click a segment to filter the dashboard.**
  1. Select sheet **3. Lead Free DC vs All Other** on the dashboard.
  2. Click its ▾ menu and choose **Use as Filter** (the funnel icon).

  Clicking "All other permits" then filters every other sheet.
- **Highlight one applicant across sheets.**
  1. Choose **Dashboard → Actions → Add Action → Highlight**.
  2. Set the source to sheet 4, the targets to sheets 8 and 2, and the run-on to **Hover**.
- **Add a filter.** On sheet 2, right-click **Ward** and choose **Show Filter**. Then add the filter to the dashboard from the sheet's ▾ menu (**Filters → Ward**) and apply it to all sheets that use this data source: on the filter, choose **▾ → Apply to Worksheets → All Using This Data Source**.

---

## 12. Final formatting checklist

- [ ] Every worksheet has a clear title (the dashboard shows sheet titles).
- [ ] Axis titles read "Avg Business Days to Approve", not `AGG(...)`. To change one, right-click the axis and choose **Edit Axis → Title**.
- [ ] Numbers show 1 decimal, and percentages show 1 decimal with %.
- [ ] Bar charts are sorted, and the order of the time bands is correct.
- [ ] Colours match across sheets: orange for Lead Free DC, blue for everything else.
- [ ] Tooltips include Permits and Median, so readers can see sample sizes. Some categories are tiny: Projections has 6 permits and Landscaping has 9.
- [ ] Gridlines are light or removed, under **Format → Lines**.
- [ ] Tab order: dashboard first. Drag its tab to the left, then right-click a sheet tab to **Hide** sheets if you like. Don't hide them for the submission; the reviewers want to see the worksheets.

---

## 13. Save and package

1. Choose **File → Save As**, set the type to **Tableau Packaged Workbook (*.twbx)**, and name it `DDOT_FY26_Permit_Approval_Times.twbx`.
   The packaged file embeds the CSV, so the reviewer doesn't need your X: drive.
2. Close and reopen the `.twbx` to confirm it loads without asking for the data file.
3. Build the submission folder:
   ```
   FirstName_MiddleInitial_LastName_Tableau\
     DDOT_FY26_Permit_Approval_Times.twbx
     APPROACH.md                      (method, findings, next steps)
     scripts\pull_permits.py, prepare_permits.py, build_workbook.py
     data\fy26_new_issued_permits.csv, dc_holidays.csv
   ```
4. Right-click the folder, choose **Send to → Compressed (zipped) folder**, and name the zip with your real name: `FirstName_MiddleInitial_LastName_Tableau.zip`.

---

## Appendix A: How the CSV was prepared (for reviewers' questions)

- **Source.** The DC GIS REST feed `DCGIS_APPS/DDOT_TOPS/MapServer/23`, queried with `ApplicationDate >= 2025-10-01` and paged 2,000 records at a time: 50,964 raw records.
- **New permits.** `RenewalDescription = "New"`. Renewals have a `-R#` suffix on the permit number.
- **Issued in FY26.** `IssueDate` between Oct 1, 2025 and Sep 30, 2026.
- **Business days.**
  - Computed with `numpy.busday_count(application date, approval date, holidays=DC holidays)`. This counts elapsed business days and excludes Saturdays, Sundays and DC holidays.
  - Holidays: Oct 13, Nov 11, Nov 27 and Dec 25, 2025; Jan 1, Jan 19, Feb 16, Apr 16 (DC Emancipation Day), May 25, Jun 19, Jul 3 (observed) and Sep 7, 2026.
- **Permit Type Category.**
  - DC Water's Lead Free DC permits always carry the same three line items: Boring Test Pit (Single), Boring Test Pit (Each Add'l), and Repair Water Service Lateral. A permit with only those items is a **Lead Service Line Replacement**.
  - Other excavation permits are grouped by keywords in their remaining line items: Gas; Water / Sewer; Electric / Telecom; Mega Project; Other Excavation.
  - Non-excavation permits use their TOPS work type: Fixture, Paving, Overhead Work, Landscaping, Projections.

## Appendix B: Doing the business-day calculation inside Tableau instead

If a reviewer wants the calculation inside Tableau, use this weekday-only formula. It counts Mon–Fri days between two dates:

```
// Weekdays between application and approval (excludes Sat/Sun, not holidays)
DATEDIFF('day', [ApplicationDate], [LastApprovalDate])
 - 2 * DATEDIFF('week', [ApplicationDate], [LastApprovalDate])
 - IIF(DATEPART('weekday', [ApplicationDate]) = 1, 1, 0)
 + IIF(DATEPART('weekday', [LastApprovalDate]) = 7, 1, 0)
```

Then subtract holidays:
1. Join or relate `dc_holidays.csv` to the permits.
2. Count the holidays that fall between the two dates, for example with a calculated field over the holiday table.
3. Subtract that count from the weekday result.

This is why the main workbook does the calculation in Python: Tableau has no built-in holiday calendar for a business-day difference.

> Week-start settings change the weekday adjustments. The formula assumes Sunday = 1, Tableau's default for the US.
