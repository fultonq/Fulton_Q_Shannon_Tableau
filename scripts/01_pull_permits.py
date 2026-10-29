"""Pull raw DDOT TOPS public space permit records from the DC GIS ArcGIS REST service.

Usage: python3 01_pull_permits.py <output permits_raw.json>

Pages through every record with ApplicationDate >= 2025-10-01 (2,000 rows per request,
up to 5 retries per page) and writes the list of attribute dicts as JSON. The feed has one
row per block location, so a permit can appear many times; 02_prepare_permits.py dedupes it.

Exits with an error, writing nothing, if a page still fails after 5 tries or if the number of
rows pulled differs from the service's own record count for the same query.
"""
import json, sys, urllib.request, urllib.parse, time
B="https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23/query"
W="ApplicationDate >= DATE '2025-10-01'"
out=sys.argv[1]

def fetch(params):
    """POST one query to the layer, retrying up to 5 times; exits if every try fails or returns an ArcGIS error."""
    q=urllib.parse.urlencode(params).encode()
    for a in range(5):
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(B,data=q),timeout=120))
            if "error" in d: raise RuntimeError(d["error"])  # ArcGIS reports errors with HTTP 200
            return d
        except Exception as e: print("retry",a+1,e); time.sleep(3)
    sys.exit(f"giving up at offset {params.get('resultOffset',0)} after 5 tries; nothing written")

expected=fetch({"where":W,"returnCountOnly":"true","f":"json"})["count"]
rows=[]; off=0
while True:
    d=fetch({"where":W,"outFields":"*","returnGeometry":"false",
        "orderByFields":"OBJECTID","resultOffset":off,"resultRecordCount":2000,"f":"json"})
    f=d.get("features",[]); rows+= [x["attributes"] for x in f]; off+=len(f)
    print(off, flush=True)
    if not f or not d.get("exceededTransferLimit") and len(f)<2000: break
if len(rows)!=expected: sys.exit(f"pulled {len(rows)} rows but the service reports {expected}; nothing written")
json.dump(rows,open(out,"w"))
print("total",len(rows))
