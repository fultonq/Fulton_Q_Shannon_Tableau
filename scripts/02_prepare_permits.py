"""Prepare a Tableau-ready, one-row-per-permit data source from the raw DDOT TOPS pull.

Usage: python3 02_prepare_permits.py <raw permits.json> <output dir>

Outputs
  permits_by_tracking_number.csv  one row per TrackingNumber (all permits applied >= 2025-10-01)
                                  with flags so Tableau can apply the FY26 "new + issued" filter
  dc_holidays.csv                 DC government holidays used in the business-day calculation
"""
import csv, json, re, sys, collections as C, datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FY_START, FY_END = dt.date(2025, 10, 1), dt.date(2026, 9, 30)

# DC government holidays (observed dates), Oct 2025 - Nov 2026
DC_HOLIDAYS = {
    dt.date(2025, 10, 13): "Indigenous Peoples' Day / Columbus Day",
    dt.date(2025, 11, 11): "Veterans Day",
    dt.date(2025, 11, 27): "Thanksgiving Day",
    dt.date(2025, 12, 25): "Christmas Day",
    dt.date(2026, 1, 1): "New Year's Day",
    dt.date(2026, 1, 19): "Martin Luther King Jr. Day",
    dt.date(2026, 2, 16): "Washington's Birthday",
    dt.date(2026, 4, 16): "DC Emancipation Day",
    dt.date(2026, 5, 25): "Memorial Day",
    dt.date(2026, 6, 19): "Juneteenth",
    dt.date(2026, 7, 3): "Independence Day (observed)",
    dt.date(2026, 9, 7): "Labor Day",
    dt.date(2026, 10, 12): "Indigenous Peoples' Day / Columbus Day",
    dt.date(2026, 11, 11): "Veterans Day",
}


def local_dt(ms):
    return None if ms is None else dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).astimezone(ET)


def business_days(start, end):
    """Business days elapsed after `start` up to and including `end` (same day = 0)."""
    if start is None or end is None:
        return None
    n, d = 0, start
    while d < end:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in DC_HOLIDAYS:
            n += 1
    return n


FAMILY_SPLIT = re.compile(r", (?=[A-Z][A-Za-z ]+; )")
EXCAVATION_GROUPS = [  # first match wins
    ("Excavation - Test Pit / Boring", ("boring", "test pit")),
    ("Excavation - Gas", ("gas",)),
    ("Excavation - Water", ("water", "fire hydrant", "valves")),
    ("Excavation - Sewer / Storm", ("sewer", "storm", "clean out")),
    ("Excavation - Electric", ("electric", "cathodic")),
    ("Excavation - Telecom", ("telecom", "handhole", "fiber", "communication")),
]


def permit_category(type_detail_names):
    details = [t.strip() for t in FAMILY_SPLIT.split(type_detail_names or "") if t.strip()]
    families = {t.split(";")[0].strip() for t in details}
    if not families:
        return "Unknown", "Unknown"
    if len(families) > 1:
        return "Multiple Work Types", "Multiple Work Types"
    fam = families.pop()
    if fam != "Excavation":
        return fam, fam
    groups = set()
    for t in details:
        low = t.lower()
        groups.add(next((g for g, keys in EXCAVATION_GROUPS if any(k in low for k in keys)), "Excavation - Other"))
    # A test pit bundled with a utility repair is classified by the utility
    if len(groups) > 1:
        groups.discard("Excavation - Test Pit / Boring")
    return "Excavation", (groups.pop() if len(groups) == 1 else "Excavation - Multiple Utilities")


def applicant_type(permittee, applicant_co):
    s = f"{permittee or ''} | {applicant_co or ''}".lower()
    if "wash gas" in s or "washington gas" in s:
        return "Utility - Washington Gas"
    if "dcwater" in s or "dc water" in s:
        return "Utility - DC Water"
    if "pepco" in s or "potomac electric" in s:
        return "Utility - Pepco"
    if any(k in s for k in ("verizon", "comcast", "crown castle", "zayo", "cellco", "teleport", "rcn", "at&t", "starpower", "lightower", "fiber")):
        return "Utility - Telecom"
    if any(k in s for k in ("department of", "ddot", "dc department", "district of columbia", "dc public", "wmata", "dc government", "u.s. ", "national park", "architect of the capitol")):
        return "Government Agency"
    return "Private / Other"


def bucket_locations(n):
    return "1 block" if n == 1 else "2-5 blocks" if n <= 5 else "6-20 blocks" if n <= 20 else "21+ blocks"


def main(raw_path, out_dir):
    rows = json.load(open(raw_path))
    by_tn = C.defaultdict(list)
    for r in rows:
        by_tn[r["TrackingNumber"]].append(r)

    out = []
    for tn, recs in by_tn.items():
        recs.sort(key=lambda r: r["OBJECTID"])
        r = recs[0]  # permit-level attributes are repeated on every block row
        app, apr, iss = (local_dt(r[k]) for k in ("ApplicationDate", "LastApprovalDate", "IssueDate"))
        wards = sorted({x["Ward"] for x in recs if x["Ward"]})
        work_family, permit_cat = permit_category(r["TypeDetailNames"])
        out.append({
            "TrackingNumber": tn,
            "PermitNumber": r["PermitNumber"],
            "Status": r["StatusDescription"],
            "NewOrRenewal": r["RenewalDescription"],
            "ApplicationDate": app.date().isoformat() if app else "",
            "ApprovalDate": apr.date().isoformat() if apr else "",
            "IssueDate": iss.date().isoformat() if iss else "",
            "IssuedInFY26": int(bool(iss) and FY_START <= iss.date() <= FY_END),
            "BusinessDaysToApprove_QA": business_days(app and app.date(), apr and apr.date()),
            "BusinessDaysToIssue_QA": business_days(app and app.date(), iss and iss.date()),
            "CalendarDaysToApprove": (apr.date() - app.date()).days if app and apr else "",
            "WorkTypeFamily": work_family,
            "PermitCategory": permit_cat,
            "TypeDetailNames": r["TypeDetailNames"],
            "NumWorkTypes": len([t for t in FAMILY_SPLIT.split(r["TypeDetailNames"] or "") if t.strip()]),
            "ApplicantType": applicant_type(r["PermitteeName"], r["ApplicantCompany"]),
            "PermitteeName": r["PermitteeName"],
            "ResubmissionRequested": "Yes" if r["LastResubmissionRequestDate"] else "No",
            "PSCReview": "Yes" if r["PCReviewStatus"] else "No",
            "NumBlockLocations": len(recs),
            "LocationBucket": bucket_locations(len(recs)),
            "Ward": wards[0] if len(wards) == 1 else ("Multiple Wards" if wards else "Unknown"),
            "Quadrant": r["Quadrant"],
            "TotalFee": r["TotalFee"],
            "Latitude": r["Latitude"],
            "Longitude": r["Longitude"],
            "WorkLocation": r["WorkLocationFullAddress"],
        })

    with open(f"{out_dir}/permits_by_tracking_number.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    with open(f"{out_dir}/dc_holidays.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["HolidayDate", "HolidayName"])
        for d, n in sorted(DC_HOLIDAYS.items()):
            w.writerow([d.isoformat(), n])
    print(f"{len(rows)} raw rows -> {len(out)} permits")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
