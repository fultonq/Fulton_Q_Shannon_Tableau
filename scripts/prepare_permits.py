"""Filter and enrich the raw permit pull into the Tableau data source.

Filters (from the request):
  * ApplicationDate on or after 2025-10-01
  * New permits only (RenewalDescription == "New"; renewals carry a -Rn suffix)
  * Issued in FY26: IssueDate between 2025-10-01 and 2026-09-30

Business days:
  Counted with numpy.busday_count over calendar dates, excluding Saturdays,
  Sundays and District of Columbia holidays (python-holidays, US/DC, which
  includes DC Emancipation Day and observed-date rules). The count is the
  number of business days elapsed after the application date, so a permit
  approved on the day it was submitted is 0 days and one approved the next
  business day is 1 day. Weekend/holiday submissions start on the next
  business day.

Outputs:
  data/fy26_new_issued_permits.csv  - one row per permit, used by Tableau
  data/dc_holidays.csv              - holidays excluded from the calculation
"""
from __future__ import annotations

import re
from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_permits.csv"
OUT = ROOT / "data" / "fy26_new_issued_permits.csv"
HOL_OUT = ROOT / "data" / "dc_holidays.csv"

FY_START, FY_END = pd.Timestamp("2025-10-01"), pd.Timestamp("2026-09-30 23:59:59")

DC_HOLIDAYS = holidays.US(subdiv="DC", years=range(2025, 2028))
HOLIDAY_DATES = np.array(sorted(DC_HOLIDAYS.keys()), dtype="datetime64[D]")

# Items that the DC Water Lead Free DC program attaches to every lead-line permit.
LEAD_BUNDLE = {
    "Excavation; Boring Test Pit (Single)",
    "Excavation; Boring Test Pit (Each Add'l)",
    "Excavation; Repair Water Service Lateral",
}

FLAG_LABELS = {
    "IsExcavation": "Excavation",
    "IsFixture": "Fixture",
    "IsPaving": "Paving",
    "IsLandscaping": "Landscaping",
    "IsProjections": "Projections",
    "IsOverHeadWork": "Overhead Work",
    "IsPSRental": "Public Space Rental",
}


def business_days(start: pd.Series, end: pd.Series) -> pd.Series:
    """Business days from start to end (weekends and DC holidays excluded); NaN where end is missing."""
    ok = start.notna() & end.notna()
    out = pd.Series(np.nan, index=start.index)
    s = start[ok].dt.normalize().values.astype("datetime64[D]")
    e = end[ok].dt.normalize().values.astype("datetime64[D]")
    out[ok] = np.busday_count(s, e, holidays=HOLIDAY_DATES)
    return out


def split_items(names: str) -> list[str]:
    # Items look like "Category; Item" and are comma separated, but some items
    # contain commas themselves, so only split where a new "Category;" begins.
    if not isinstance(names, str) or not names.strip():
        return []
    return [p.strip() for p in re.split(r",\s*(?=[A-Z][A-Za-z ]+;)", names) if p.strip()]


def permit_category(row: pd.Series) -> str:
    kinds = [label for flag, label in FLAG_LABELS.items() if row.get(flag, 0) == 1]
    if not kinds:
        return "Unspecified"
    return kinds[0] if len(kinds) == 1 else "Multiple Work Types"


def work_focus(items: list[str], category: str) -> str:
    """A finer grouping of what the permit is for, from its line items."""
    specific = [i for i in items if i not in LEAD_BUNDLE]
    if items and not specific:
        return "Lead Service Line Replacement"
    text = " ".join(specific).lower()
    if category not in ("Excavation", "Multiple Work Types"):
        return category
    if "mega projects" in text:
        return "Mega Project"
    if "gas" in text:
        return "Gas Utility Work"
    if re.search(r"water|sewer|storm|hydrant|valve|meter pit|clean out|doee", text):
        return "Water / Sewer Work"
    if re.search(r"electric|telecom|handhole|manhole|conduit|cathodic|pole", text):
        return "Electric / Telecom Work"
    return "Other Excavation"


def applicant_group(company: str, work_detail: str) -> str:
    c = (company or "").lower()
    if "dcwater" in c or "dc water" in c:
        return "DC Water (Lead Free DC)" if "lead free" in (work_detail or "").lower() else "DC Water (Other)"
    if "gas" in c:
        return "Washington Gas"
    if "pepco" in c or "potomac electric" in c:
        return "Pepco"
    if re.search(r"verizon|comcast|zayo|crown castle|cellco|rcn|starpower|teleport|at&t|t-mobile|fiber|telecom|lightower|cogent", c):
        return "Telecom"
    if re.search(r"ddot|department|district|government|dgs|u\.s\.|marine|federal|wmata|national park|army|navy|agency", c):
        return "Government / Agency"
    if not c:
        return "Not Recorded"
    return "Private / Other"


def bucket(days: float) -> str:
    if pd.isna(days):
        return "Not Approved"
    for upper, label in [(0, "01) Same day"), (5, "02) 1-5 days"), (10, "03) 6-10 days"),
                         (20, "04) 11-20 days"), (40, "05) 21-40 days"), (60, "06) 41-60 days")]:
        if days <= upper:
            return label
    return "07) Over 60 days"


def main() -> None:
    dates = ["ApplicationDate", "IntakeDate", "ReadyForReviewDate", "AssignedDate",
             "LastApprovalDate", "IssueDate", "EffectiveDate", "ExpirationDate", "PermitFeesPaymentDate"]
    raw = pd.read_csv(RAW, low_memory=False, parse_dates=dates)

    df = raw[(raw.ApplicationDate >= FY_START)
             & (raw.RenewalDescription == "New")
             & raw.IssueDate.between(FY_START, FY_END)].copy()
    print(f"raw {len(raw)} -> new, applied & issued in FY26: {len(df)}")

    df["BusDaysToAssign"] = business_days(df.ApplicationDate, df.AssignedDate)
    df["BusDaysToApprove"] = business_days(df.ApplicationDate, df.LastApprovalDate)
    df["BusDaysApproveToIssue"] = business_days(df.LastApprovalDate, df.IssueDate)
    df["BusDaysToIssue"] = business_days(df.ApplicationDate, df.IssueDate)

    items = df.TypeDetailNames.apply(split_items)
    df["PermitCategory"] = df.apply(permit_category, axis=1)
    df["WorkFocus"] = [work_focus(i, c) for i, c in zip(items, df.PermitCategory)]
    df["LineItemCount"] = items.str.len()
    df["ApplicantGroup"] = [applicant_group(c, w) for c, w in zip(df.ApplicantCompany.fillna(""), df.WorkDetail.fillna(""))]
    df["LeadFreeDC"] = np.where(df.ApplicantGroup == "DC Water (Lead Free DC)", "Lead Free DC program", "All other permits")
    df["ApprovalBucket"] = df.BusDaysToApprove.apply(bucket)
    df["ApplicationMonth"] = df.ApplicationDate.dt.to_period("M").dt.to_timestamp()
    df["IssueMonth"] = df.IssueDate.dt.to_period("M").dt.to_timestamp()
    df["Ward"] = df.Ward.apply(lambda w: f"Ward {int(w)}" if pd.notna(w) else "Unknown")
    df["Quadrant"] = df.Quadrant.fillna("Unknown")
    df["ReviewedByPublicSpaceCommittee"] = np.where(df.PCReviewStatus.notna(), "Yes", "No")
    df["SameDayApproval"] = (df.BusDaysToApprove == 0).astype(int)

    keep = ["OBJECTID", "TrackingNumber", "PermitNumber", "StatusDescription", "RenewalDescription",
            "ApplicationDate", "AssignedDate", "LastApprovalDate", "IssueDate", "EffectiveDate", "ExpirationDate",
            "ApplicationMonth", "IssueMonth",
            "DaysToAssign", "DaysToApprove", "DaysToIssue",
            "BusDaysToAssign", "BusDaysToApprove", "BusDaysApproveToIssue", "BusDaysToIssue",
            "ApprovalBucket", "SameDayApproval",
            "PermitCategory", "WorkFocus", "LineItemCount", "TypeDetailNames",
            "ApplicantCompany", "ApplicantGroup", "LeadFreeDC", "ReviewedByPublicSpaceCommittee",
            "TotalFee", "PermitFee", "Ward", "Quadrant", "WorkLocationZip", "NeighborhoodNames",
            "HistoricDistrict", "Latitude", "Longitude"]
    out = df[keep].sort_values("ApplicationDate")
    for c in out.select_dtypes("datetime").columns:
        out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    for c in ["ApplicationMonth", "IssueMonth"]:
        out[c] = out[c].str[:10]
    # Whole-number columns with gaps would otherwise be written as "12.0".
    for c in ["TrackingNumber", "DaysToAssign", "DaysToApprove", "DaysToIssue", "BusDaysToAssign",
              "BusDaysToApprove", "BusDaysApproveToIssue", "BusDaysToIssue", "LineItemCount"]:
        out[c] = out[c].round().astype("Int64")
    out["WorkLocationZip"] = pd.to_numeric(out.WorkLocationZip, errors="coerce").astype("Int64").astype("string")
    out.to_csv(OUT, index=False)

    pd.DataFrame(sorted(DC_HOLIDAYS.items()), columns=["Date", "Holiday"]).to_csv(HOL_OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")

    # Quick summary for the narrative.
    a = out.BusDaysToApprove
    print(f"\nOverall: n={a.notna().sum()} mean={a.mean():.2f} median={a.median():.1f} "
          f"same-day={(a == 0).mean():.1%}  to-issue mean={out.BusDaysToIssue.mean():.2f}")
    for col in ["PermitCategory", "WorkFocus", "ApplicantGroup", "LeadFreeDC", "Ward",
                "ReviewedByPublicSpaceCommittee", "ApplicationMonth", "ApprovalBucket"]:
        g = out.groupby(col).agg(permits=("OBJECTID", "size"), avg_approve=("BusDaysToApprove", "mean"),
                                 median=("BusDaysToApprove", "median"), avg_issue=("BusDaysToIssue", "mean"))
        print(f"\n== {col}\n{g.round(2).sort_values('permits', ascending=False).to_string()}")


if __name__ == "__main__":
    main()
