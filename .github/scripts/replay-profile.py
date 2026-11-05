"""Change just the compiled speed profile in a temporary copy of the production tiles."""
import hashlib
import json
import subprocess
import time
import urllib.request
import sys

from airport_edge import A, B, C, D, OUTPUT, route, request, trace
def command(*args):
    subprocess.run(["docker","exec","airport-audit",*args],check=True)
def start(config):
    subprocess.run(["docker","exec","-d","airport-audit","sh","-c","echo $$ >/tmp/service.pid; exec valhalla_service "+config+" 1 >/tmp/replay-service.log 2>&1"],check=True)
    for _ in range(45):
        try:
            if request("GO","status",None).get("version"): return
        except Exception: pass
        time.sleep(1)
    command("sh","-c","cat /tmp/replay-service.log; ls -l /tmp/*json /tmp/*.tar; ps -ef | head -30")
    raise RuntimeError("local service did not start")
def read_route_shapes():
    return [route("GO",[A,B],"mall-terminal"),route("GO",[C,D],"first-expressway")]
def inspect(shape, label):
    data={"costing":"auto","units":"kilometers","shape_match":"edge_walk","encoded_polyline":shape,"filters":{"action":"include","attributes":["edge.length","edge.speed","edge.speed_type","edge.speeds_non_faded","edge.road_class","edge.use","edge.speed_limit","edge.density","node.elapsed_time","node.transition_time"]}}
    q=request("GO","trace_attributes",data); edges=q["edges"]; totals={}
    for e in edges:
        key=(e.get("speed"),e.get("speed_limit"),e.get("speed_type"),e.get("road_class"),e.get("use"),e.get("density"))
        totals[key]=totals.get(key,0)+e["length"]
    OUTPUT("DETAIL",[label,edges[-1]["end_node"],[[k,round(v,3)] for k,v in totals.items()]])
cfg="""import json
base=json.load(open('/data/config.json'))
base['loki']['actions'].append('trace_attributes')
json.dump(base,open('/tmp/original.json','w'))
print('ORIGINAL_CONFIG', {k:base['mjolnir'].get(k) for k in ['default_speeds_config','tile_extract','tile_dir']})
base['mjolnir'].pop('tile_extract',None)
base['mjolnir']['tile_dir']='/tmp/trial-tiles'
base['mjolnir']['default_speeds_config']='/tmp/community-profile.json'
json.dump(base,open('/tmp/calibrated.json','w'))"""
command("python3","-c",cfg)
start("/tmp/original.json")
OUTPUT("PHASE","original")
original,corridor=read_route_shapes()
inspect(corridor,"before")
command("sh","-c","kill $(cat /tmp/service.pid); mkdir -p /tmp/trial-tiles && tar xf /data/tiles.tar -C /tmp/trial-tiles")
command("valhalla_assign_speeds","-c","/tmp/calibrated.json","-j","1")
command("python3","-c","import json; p='/tmp/calibrated.json'; c=json.load(open(p)); c['mjolnir']['tile_extract']='/tmp/adjusted.tar'; json.dump(c,open(p,'w'))")
command("valhalla_build_extract","-c","/tmp/calibrated.json")
subprocess.run(["docker","restart","airport-audit"],check=True)
start("/tmp/calibrated.json")
OUTPUT("PHASE","open-profile")
changed,changed_corridor=read_route_shapes()
inspect(corridor,"after-fixed-corridor")
trace("GO",original,"after-fixed-original-full-path")
trace("GO",changed,"after-selected-full-path")
