"""Pull DDOT Public Space Construction Permits from the DC GIS REST feed.

Downloads every permit with an application date on or after 2025-10-01 (start of
FY26) from MapServer layer 23, paging through the service's record limit, and
writes the raw records to data/raw_permits.csv. Dates arrive as epoch
milliseconds (UTC) and are converted to US/Eastern local dates.

Usage:  python pull_permits.py
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

LAYER = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23"
WHERE = "ApplicationDate >= DATE '2025-10-01'"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw_permits.csv"

# Free-text and geometry-helper fields we don't need for the analysis.
DROP = {"Shape", "WorkLocationLot", "WorkLocationSquare", "OwnerName", "PermitteeName"}


def get(url: str, params: dict) -> dict:
    for attempt in range(5):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            if attempt == 4:
                raise
            print(f"  retry {attempt + 1}: {exc}")
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def main() -> None:
    meta = get(LAYER, {"f": "json"})
    date_fields = [f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeDate"]
    fields = [f["name"] for f in meta["fields"] if f["name"] not in DROP]
    page = int(meta.get("maxRecordCount", 1000))

    total = get(f"{LAYER}/query", {"where": WHERE, "returnCountOnly": "true", "f": "json"})["count"]
    print(f"{total} permits match: {WHERE}")

    rows: list[dict] = []
    offset = 0
    while offset < total:
        data = get(f"{LAYER}/query", {
            "where": WHERE,
            "outFields": ",".join(fields),
            "returnGeometry": "false",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": page,
            "f": "json",
        })
        batch = [feat["attributes"] for feat in data["features"]]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        print(f"  fetched {offset}/{total}")

    df = pd.DataFrame(rows).drop_duplicates("OBJECTID")
    for col in date_fields:
        if col in df:
            df[col] = (pd.to_datetime(df[col], unit="ms", utc=True)
                       .dt.tz_convert("America/New_York").dt.tz_localize(None))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} rows to {OUT}")


if __name__ == "__main__":
    main()
