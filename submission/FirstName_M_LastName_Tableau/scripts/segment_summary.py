"""Build a purpose-built segment comparison table for Tableau.

For every segment of several dimensions, compare the segment's average business
days to approve with the FY26 overall average, and flag where the difference is
meaningful. A difference counts as meaningful when the segment has at least
MIN_PERMITS permits and its average differs from the overall average by at
least MEANINGFUL_DAYS business days (about a week and a half).

Because Lead Free DC permits are 84% of the data, each segment is also compared
within "All other permits", so a difference isn't just program mix.

Output: data/segment_comparison.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "fy26_new_issued_permits.csv"
OUT = ROOT / "data" / "segment_comparison.csv"

MIN_PERMITS = 30
MEANINGFUL_DAYS = 7.0

DIMENSIONS = {
    "Permit Type Category": "WorkFocus",
    "Applicant Group": "ApplicantGroup",
    "Lead Free DC Program": "LeadFreeDC",
    "Ward": "Ward",
    "Quadrant": "Quadrant",
    "Public Space Committee Review": "ReviewedByPublicSpaceCommittee",
    "Application Quarter": "ApplicationQuarter",
    "Historic District": "InHistoricDistrict",
    "Line Items on Permit": "LineItemBand",
}


def add_fields(df: pd.DataFrame) -> pd.DataFrame:
    app = pd.to_datetime(df.ApplicationDate)
    # Fiscal quarter: FY26 Q1 = Oct-Dec 2025.
    fq = ((app.dt.month - 10) % 12) // 3 + 1
    df["ApplicationQuarter"] = "FY26 Q" + fq.astype(str)
    df["InHistoricDistrict"] = np.where(df.HistoricDistrict.notna(), "In a historic district", "Not in a historic district")
    df["LineItemBand"] = pd.cut(df.LineItemCount.fillna(0), [-1, 1, 3, 1000],
                                labels=["1 line item", "2-3 line items", "4+ line items"]).astype(str)
    return df


def summarise(df: pd.DataFrame, scope: str) -> list[dict]:
    overall = df.BusDaysToApprove.mean()
    rows = []
    for dim_label, col in DIMENSIONS.items():
        for value, g in df.groupby(col):
            d = g.BusDaysToApprove.dropna()
            if d.empty:
                continue
            diff = d.mean() - overall
            n = len(g)
            meaningful = n >= MIN_PERMITS and abs(diff) >= MEANINGFUL_DAYS
            rows.append({
                "Scope": scope,
                "Dimension": dim_label,
                "Segment": str(value),
                "Permits": n,
                "PctOfScope": n / len(df),
                "AvgBusDaysToApprove": round(d.mean(), 2),
                "MedianBusDaysToApprove": float(d.median()),
                "P25": float(d.quantile(.25)),
                "P75": float(d.quantile(.75)),
                "ScopeAverage": round(overall, 2),
                "DiffFromAverage": round(diff, 2),
                "PctDiffFromAverage": round(diff / overall, 4),
                "AvgBusDaysToIssue": round(g.BusDaysToIssue.mean(), 2),
                "Direction": "Slower than average" if diff > 0 else "Faster than average",
                "Meaningful": "Meaningful difference" if meaningful
                else ("Too few permits" if n < MIN_PERMITS else "Close to average"),
            })
    return rows


def main() -> None:
    df = add_fields(pd.read_csv(SRC))
    rows = summarise(df, "All FY26 permits") + summarise(df[df.LeadFreeDC == "All other permits"],
                                                        "Excluding Lead Free DC")
    out = pd.DataFrame(rows)
    out["Flag"] = np.select(
        [out.Meaningful.eq("Meaningful difference") & out.DiffFromAverage.gt(0),
         out.Meaningful.eq("Meaningful difference") & out.DiffFromAverage.lt(0)],
        ["Meaningfully slower", "Meaningfully faster"], "Within 7 days of average")
    out["SegmentLabel"] = out.Dimension + ": " + out.Segment
    # Tableau view: segments with enough permits; the program split is the scope itself when excluding it.
    out = out[(out.Permits >= MIN_PERMITS)
              & ~((out.Scope == "Excluding Lead Free DC") & (out.Dimension == "Lead Free DC Program"))]
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} segment rows to {OUT}")
    pd.set_option("display.width", 200)
    for scope, g in out.groupby("Scope"):
        print(f"\n=== {scope} (avg {g.ScopeAverage.iloc[0]})")
        m = g[g.Meaningful == "Meaningful difference"].sort_values("DiffFromAverage")
        print(m[["Dimension", "Segment", "Permits", "AvgBusDaysToApprove", "MedianBusDaysToApprove", "DiffFromAverage"]]
              .to_string(index=False))


if __name__ == "__main__":
    main()
