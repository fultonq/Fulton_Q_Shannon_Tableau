import sys
from pathlib import Path
import pandas as pd

pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_colwidth", 80)
df = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "raw_permits.csv", low_memory=False)
print(df.shape)
for c in ["StatusDescription", "PermitTypeDescription", "PermitType", "RenewalDescription", "Renewal", "FiscalYear",
          "PCReviewStatus", "ReviewProcess", "ProcessNumber", "IsAnnualPermit", "Ward", "Quadrant"]:
    print("\n==", c); print(df[c].value_counts(dropna=False).head(25).to_string())
print("\nSourcePermit null:", df.SourcePermit.isna().mean())
print("\nPermit number prefixes:"); print(df.PermitNumber.astype(str).str.extract(r"^([A-Za-z]+)")[0].value_counts(dropna=False).head(20))
print("\nIssueDate non-null:", df.IssueDate.notna().sum())
for c in ["IsExcavation","IsFixture","IsPaving","IsOccupancy","IsLandscaping","IsProjections","IsPSRental","IsOverHeadWork"]:
    print(c, int(df[c].fillna(0).sum()))
print(df[["DaysToAssign","DaysToApprove","DaysToIssue"]].describe())
td = df.TypeDetailNames.dropna().str.split(r"\s*,\s*").explode()
print("\nTop TypeDetailNames:"); print(td.value_counts().head(40).to_string())
print(df[["PermitNumber","ApplicationDate","IntakeDate","ReadyForReviewDate","AssignedDate","LastApprovalDate","IssueDate","DaysToApprove","DaysToIssue","StatusDescription"]].sample(12, random_state=1).to_string())
