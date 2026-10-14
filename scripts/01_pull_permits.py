import json, sys, urllib.request, urllib.parse, time
B="https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/23/query"
out=sys.argv[1]  # usage: python3 01_pull_permits.py permits_raw.json; rows=[]; off=0
while True:
    q=urllib.parse.urlencode({"where":"ApplicationDate >= DATE '2025-10-01'","outFields":"*","returnGeometry":"false",
        "orderByFields":"OBJECTID","resultOffset":off,"resultRecordCount":2000,"f":"json"})
    for a in range(5):
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(B,data=q.encode()),timeout=120)); break
        except Exception as e: print("retry",e); time.sleep(3)
    f=d.get("features",[]); rows+= [x["attributes"] for x in f]; off+=len(f)
    print(off, flush=True)
    if not f or not d.get("exceededTransferLimit") and len(f)<2000: break
json.dump(rows,open(out,"w"))
print("total",len(rows))
