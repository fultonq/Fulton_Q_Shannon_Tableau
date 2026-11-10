from pathlib import Path
import pandas as pd
import holidays

pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_colwidth", 90)
df = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "raw_permits.csv", low_memory=False,
                 parse_dates=["ApplicationDate", "LastApprovalDate", "IssueDate", "AssignedDate", "ReadyForReviewDate"])
s = df[(df.RenewalDescription == "New") & df.IssueDate.between("2025-10-01", "2026-09-30 23:59:59")]
print("new & issued FY26:", len(s), " app>=10/1 all true:", (s.ApplicationDate >= "2025-10-01").all())
print(s.StatusDescription.value_counts().to_string())
print("FiscalYear:", s.FiscalYear.value_counts().to_dict(), " PermitType:", s.PermitTypeDescription.value_counts(dropna=False).to_dict())
print("LastApprovalDate null:", s.LastApprovalDate.isna().sum(), " approval>issue:", (s.LastApprovalDate > s.IssueDate).sum())
print("permit number has -R:", s.PermitNumber.str.contains("-R").sum(), " SourcePermit notnull:", s.SourcePermit.notna().sum())
flags = ["IsExcavation","IsFixture","IsPaving","IsLandscaping","IsProjections","IsPSRental","IsOverHeadWork"]
print(s[flags].sum().to_string())
print("flag combos:"); print(s[flags].astype(int).astype(str).agg("".join, axis=1).value_counts().head(15).to_string())
DEFAULTS = {"Excavation; Boring Test Pit (Single)", "Excavation; Boring Test Pit (Each Add'l)", "Excavation; Repair Water Service Lateral"}
td = s.TypeDetailNames.fillna("").str.split(r"\s*,\s*")
n_def = td.apply(lambda l: sum(x in DEFAULTS for x in l))
print("default items count dist:", n_def.value_counts().to_dict())
other = td.apply(lambda l: [x for x in l if x and x not in DEFAULTS])
print("permits with only default items:", (other.str.len() == 0).sum())
print(other.explode().value_counts().head(50).to_string())
print("\nApplicantCompany top:"); print(s.ApplicantCompany.value_counts(dropna=False).head(25).to_string())
print("\nDaysToApprove check vs calendar:", ((s.LastApprovalDate.dt.normalize() - s.ApplicationDate.dt.normalize()).dt.days - s.DaysToApprove).describe())
print(s.WorkDetail.dropna().sample(8, random_state=2).str[:150].to_string())
print(sorted(holidays.US(subdiv="DC", years=[2025, 2026]).items()))
