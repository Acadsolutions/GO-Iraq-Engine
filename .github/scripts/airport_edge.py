"""Read-only appraisal using two public landmark routes; no driver data."""
import collections
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request

SERVICE = "http://127.0.0.1:8002/"
PUBLIC = "https://valhalla1.openstreetmap.de/"
A = [44.3643733, 33.3119122]
B = [44.2300198, 33.2677518]
C = [44.346636, 33.286927]
D = [44.254068, 33.268854]
OUTPUT = lambda label, data: print(label, json.dumps(data, ensure_ascii=False), flush=True)
LOCAL = """import json, sys, urllib.request, urllib.error
action, data = json.load(sys.stdin)
req = urllib.request.Request('http://127.0.0.1:8002/'+action, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(req, timeout=24) as r: print(r.read().decode())
except urllib.error.HTTPError as ex: print(ex.read().decode())
"""
HEADERS = {"Accept":"application/json", "Content-Type":"application/json", "User-Agent":"GO Iraq research (ACAD Solutions; https://acadsolutions.nl; info@acadsolutions.nl)", "X-Client-Id":"acadsolutions.nl/darb-public-prototype"}
last_public = 0
blocked = False
def request(server, action, data):
    global last_public, blocked
    if server == "GO":
        proc = subprocess.run(["docker","exec","-i","airport-audit","python3","-c",LOCAL],input=json.dumps([action,data]), text=True, capture_output=True, timeout=32)
        if proc.returncode: raise RuntimeError(proc.stderr[-350:])
        return json.loads(proc.stdout)
    if blocked: return {"error":"public reference skipped"}
    time.sleep(max(0, 2.2 - (time.monotonic() - last_public)))
    last_public = time.monotonic()
    req=urllib.request.Request(PUBLIC+action, data=json.dumps(data).encode() if data is not None else None, headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=24) as res: return json.load(res)
    except urllib.error.HTTPError as ex:
        if ex.code in (403,429): blocked=True
        return {"error": ex.code, "reason":ex.read(400).decode(errors="replace")}
    except OSError as ex:
        blocked=True
        return {"error":str(ex)}
def locations(coords):
    return [{"lon": lon, "lat": lat, "type":"break"} for lon,lat in coords]
def route(server, points, label):
    response=request(server,"route",{"locations":locations(points),"costing":"auto","units":"kilometers","language":"en-US","alternates":0,"directions_type":"instructions","turn_lanes":True})
    if "trip" not in response:
        OUTPUT("ROUTE_ERROR", [server,label,response]); return None
    trip=response["trip"];leg=trip["legs"][0]
    OUTPUT("ROUTE",[server,label,trip["summary"]["length"],trip["summary"]["time"],hashlib.sha256(leg["shape"].encode()).hexdigest(),[(m.get("street_names",[]),m["length"],m["time"]) for m in leg["maneuvers"]]])
    return leg["shape"]
ATTR=["edge.way_id","edge.speed","edge.speed_type","edge.speed_limit","edge.default_speed","edge.speeds_non_faded","edge.length","edge.road_class","edge.use","edge.density","node.elapsed_time","node.transition_time","node.traffic_signal","edge.traffic_signal","edge.begin_osm_node_id","edge.end_osm_node_id"]
def trace(server, shape, label, detailed=False):
    if not shape: return
    data={"costing":"auto","units":"kilometers","shape_match":"edge_walk","encoded_polyline":shape,"filters":{"action":"include","attributes":ATTR}}
    result=request(server,"trace_attributes",data)
    if not result.get("edges"):
        OUTPUT("TRACE_ERROR",[server,label,{k:result.get(k) for k in ["error","error_code","reason"]}]);return
    edges=result["edges"]
    # edge_walk is exact matching; any failure is reported instead of silently snapping a competing path.
    counts=collections.Counter(); ids=[]; raw=[]
    for e in edges:
        way=e.get("way_id")
        if way and (not ids or way!=ids[-1]): ids.append(way)
        if detailed:
            profile={k:e.get(k) for k in ["speed","speed_type","speed_limit","default_speed","speeds_non_faded","road_class"]}
            counts[json.dumps(profile,sort_keys=True)]+=e.get("length",0)
            raw.append([way,e.get("begin_osm_node_id"),e.get("end_osm_node_id"),e.get("length"),e.get("speed"),e.get("speed_type"),e.get("speed_limit"),e.get("speeds_non_faded")])
    OUTPUT("TRACE",[server,label,len(edges),round(sum(e.get("length",0) for e in edges),3),edges[-1].get("end_node"),round(sum(e.get("end_node",{}).get("transition_time",0) for e in edges),3),hashlib.sha256(json.dumps(ids).encode()).hexdigest()])
    if detailed:
        OUTPUT("PROFILES",[server,label,[[json.loads(k),round(l,3)] for k,l in counts.items()]])
        OUTPUT("EDGES",[server,label,raw])
    return ids
if __name__ == "__main__":
    for attempt in range(25):
        try:
            if request("GO","status",None).get("version"): break
        except Exception: pass
        time.sleep(1)
    for server in ["GO","PUBLIC"]:
        info=request(server,"status",None)
        OUTPUT("VERSION",[server,{k:info.get(k) for k in ("version","tileset_last_modified","error")}])
    routes={}
    for server in ["GO","PUBLIC"]:
        routes[server]=route(server,[A,B],"mall-terminal")
        routes[server+"corridor"]=route(server,[C,D],"first-expressway")
    for server in ["GO","PUBLIC"]:
        for origin in ["GO","PUBLIC"]:
            trace(server, routes[origin], "full-geometry-"+origin)
        trace(server,routes["GOcorridor"],"identical-expressway",detailed=True)
        if server=="GO" and routes["PUBLICcorridor"]!=routes["GOcorridor"]:
            trace(server,routes["PUBLICcorridor"],"other-expressway",detailed=True)
