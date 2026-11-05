"""Trusted test-wide restrictions shared by the public GO route and traffic console."""
import base64
import hashlib
import json
import math
import os
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from direction import decode
from territory import inside_iraq

FEED = 'https://www.acadsolutions.nl/go-iraq/traffic/api.php?action=engineFeed'
ENABLED = os.environ.get('GO_TRAFFIC_CONTROL') == '1'
lock = threading.Lock()
cached = None
checked = 0.0

class TrafficError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def feed(force=False):
    global checked, cached
    with lock:
        now = time.monotonic()
        if not force and cached is not None and now-checked < 2 and (not cached.get('nextChange') or cached['nextChange'] > time.time()):
            return cached
        try:
            with urlopen(FEED, timeout=4) as response:
                if response.geturl()!=FEED: raise ValueError('unexpected feed origin')
                raw=response.read(4_000_001)
                if len(raw)>4_000_000: raise ValueError('registry size')
                data=json.loads(raw)
            if data.get('service')!='go-iraq-traffic-v2' or not isinstance(data.get('closures'),list) or not isinstance(data.get('revision'),int):
                raise ValueError('invalid registry')
        except (OSError, ValueError) as exc:
            # Never silently discard a known restriction.
            raise TrafficError(503,'تعذّر التحقق من حالة القطوعات.') from exc
        cached,checked=data,time.monotonic()
        return cached

def signed(path, raw, headers):
    try:
        stamp=headers.get('X-Go-Time','')
        if abs(time.time()-int(stamp))>45:return False
        signature=base64.b64decode(headers.get('X-Go-Signature',''),validate=True)
        if len(signature)!=256:return False
        message=(stamp+'\n'+path+'\n').encode()+raw
        pem=feed()['publicKey'].encode()
        with tempfile.NamedTemporaryFile() as key, tempfile.NamedTemporaryFile() as sig:
            key.write(pem);key.flush();sig.write(signature);sig.flush()
            return subprocess.run(['openssl','dgst','-sha256','-verify',key.name,'-signature',sig.name],
                                  input=message,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2).returncode==0
    except (ValueError,KeyError,OSError,subprocess.TimeoutExpired):return False

def iraqi(p):
    return isinstance(p,list) and len(p)==2 and all(type(x) in (int,float) and math.isfinite(x) for x in p) and inside_iraq(*p)

def native(action,payload):
    req=Request('http://127.0.0.1:8002/'+action,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=18) as response:
        data=response.read(4_000_001)
    if len(data)>4_000_000:raise TrafficError(503,'الاستجابة كبيرة.')
    return json.loads(data)

def project(p,shape):
    scale=math.cos(math.radians(p[1]))
    candidates=[]
    for a,b in zip(shape,shape[1:]):
        x,y=(b[0]-a[0])*scale,b[1]-a[1]
        fraction=max(0,min(1,((p[0]-a[0])*scale*x+(p[1]-a[1])*y)/(x*x+y*y or 1)))
        q=[round(a[k]+fraction*(b[k]-a[k]),6) for k in (0,1)]
        candidates.append((math.hypot((p[0]-q[0])*scale,p[1]-q[1]),q,round(math.degrees(math.atan2(x,y)))%360))
    return min(candidates,key=lambda c:c[0])

def locate(p):
    if not iraqi(p):raise TrafficError(400,'اختر موضعًا داخل العراق.')
    result=native('locate',{'locations':[{'lon':p[0],'lat':p[1]}],'costing':'auto','verbose':True})
    found={}
    for item in (result[0].get('edges') or []):
        edge,info=item['edge'],item['edge_info']
        if not edge['access']['car'] or item['distance']>35:continue
        key=str(info['way_id'])+':'+hashlib.sha256(info['shape'].encode()).hexdigest()[:20]
        if key not in found:
            shape=[[lon,lat] for lat,lon in decode(info['shape'])]
            if len(shape)<2:continue
            distance,pin,bearing=project(p,shape)
            found[key]={'id':key,'way':info['way_id'],'name':' / '.join(info['names']) or 'شارع محلي','shape':shape,
                        'pin':pin,'bearing':bearing,'meters':edge['geo_attributes']['length'],'distance':round(distance*111000,2),'directions':{}}
        found[key]['directions']['forward' if edge['forward'] else 'reverse']=str(item['edge_id']['value'])
    return sorted(found.values(),key=lambda s:s['distance'])[:6]

def restrictions(items):
    blocked={}
    for item in items:
        segment=item['segment']
        for direction,edge in segment['directions'].items():
            if item['direction'] in ('both',direction):
                shape=segment['shape']
                blocked[edge]=shape if direction=='forward' else shape[::-1]
    return blocked

def apply(payload,blocked):
    if len(blocked)>1024:raise TrafficError(503,'عدد القطوعات يتجاوز الحد المتاح للمحرك.')
    return {**payload,'linear_cost_factors':list(payload.get('linear_cost_factors',[]))+[
        {'type':'Feature','properties':{'factor':0},'geometry':{'type':'LineString','coordinates':shape}}
        for shape in blocked.values()]}

def walk(leg,costing):
    trace=native('trace_attributes',{'encoded_polyline':leg['shape'],'shape_match':'edge_walk','costing':costing,
        'filters':{'action':'include','attributes':['edge.id','edge.begin_shape_index','edge.end_shape_index']}})
    return [{'id':str(e['id']),'begin':e['begin_shape_index'],'end':e['end_shape_index']} for e in trace.get('edges',[])]

def filtered(payload,blocked,compact=False):
    raw=native('route',apply(payload,blocked) if blocked else payload)
    if any(w.get('code') in (212,216) for w in raw.get('warnings',[])):
        raise TrafficError(503,'تعذّر تطبيق جميع القطوعات.')
    choices=[];seen=set()
    for trip in [raw['trip']]+[a.get('trip',a) for a in raw.get('alternates',[])]:
        key=tuple(leg['shape'] for leg in trip['legs'])
        if key in seen:continue
        seen.add(key)
        try: walks=[walk(leg,payload['costing']) for leg in trip['legs']]
        except HTTPError as e:
            if e.code==400:continue
            raise
        if not walks or any(not edges or any(e['id'] in blocked for e in edges) for edges in walks):continue
        if compact:
            choices.append({'shape':[[lon,lat] for lat,lon in decode(key[0])],'edges':walks[0],
                'km':trip['summary']['length'],'seconds':trip['summary']['time']})
        else:choices.append(trip)
    if not choices:raise TrafficError(422,'لا يوجد مسار مفتوح يمكن التحقق منه.')
    if compact:return choices
    return {**raw,'trip':choices[0],'alternates':[{'trip':t} for t in choices[1:]]}

def ordinary_blocks(payload):
    if not ENABLED or payload.get('costing') not in ('auto','taxi','motorcycle','truck','bus','auto_shorter'):return {}
    if not any(iraqi([p.get('lon'),p.get('lat')]) for p in payload.get('locations',[]) if isinstance(p,dict)):return {}
    return restrictions(feed()['closures'])

def console(path,body):
    if path=='/traffic/segments':return locate(body.get('point'))
    snapshot=feed(force=path=='/traffic/sync')
    if path=='/traffic/sync':return {'enabled':ENABLED,'revision':snapshot['revision'],'version':snapshot['version']}
    origin,destination=body.get('origin'),body.get('destination')
    if not iraqi(origin) or not iraqi(destination):raise TrafficError(400,'اختر نقطتين داخل العراق.')
    payload={'locations':[{'lon':x,'lat':y} for x,y in (origin,destination)],'costing':'auto','alternates':3,
             'units':'kilometers','shape_format':'polyline6'}
    return {'routes':filtered(payload,restrictions(snapshot['closures']),True),'version':snapshot['version']}
