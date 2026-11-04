"""Small authenticated, bounded gateway. Never log request paths, bodies or coordinates."""
import hmac, json, math, os, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from direction import directional_choices, DirectionUnavailable

KEY = os.environ.get("GO_ROUTING_KEY", "")
SLOTS = threading.BoundedSemaphore(2)
UPSTREAM = "http://127.0.0.1:8002"
MAX_BODY = 262144
MAX_REPLY = 4000000

def authenticated(value):
    return bool(KEY) and hmac.compare_digest(value.encode('utf-8'), ('Bearer ' + KEY).encode('utf-8'))

def validated_payload(payload, route=False):
    if not isinstance(payload, dict): raise ValueError()
    if route:
        count = payload.get('alternates', 3)
        locations = payload.get('locations')
        if type(count) is not int or count < 0 or count > 3: raise ValueError()
        if not isinstance(locations, list) or not 2 <= len(locations) <= 6: raise ValueError()
        if not isinstance(locations[0], dict): raise ValueError()
        if 'heading' in locations[0]:
            start = locations[0]
            for key, lower, upper in [('lat', -90, 90), ('lon', -180, 180), ('heading', 0, 360)]:
                value = start.get(key)
                if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper: raise ValueError()
        payload = dict(payload)
        payload['alternates'] = 0 if len(locations) > 2 else count
    return payload

def route_choices(payload):
    """Keep at most four actual, distinct road geometries; never synthesize routes."""
    if not isinstance(payload, dict) or "trip" not in payload:
        return payload
    result = dict(payload)
    seen = set()
    trips = []
    for item in [payload["trip"]] + [a.get("trip", a) for a in payload.get("alternates", []) if isinstance(a, dict)]:
        if not isinstance(item, dict): continue
        geometry = tuple(leg.get("shape") for leg in item.get("legs", []) if isinstance(leg, dict))
        if not geometry or not all(isinstance(shape, str) and shape for shape in geometry) or geometry in seen: continue
        seen.add(geometry); trips.append(item)
        if len(trips) == 4: break
    if trips:
        result["trip"] = trips[0]
        result["alternates"] = [{"trip": trip} for trip in trips[1:]]
    return result

class Handler(BaseHTTPRequestHandler):
    server_version = "GO-Iraq"
    def log_message(self, *_): pass
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def reply(self, status, body, retry=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if retry: self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path != "/health": return self.reply(404, b'{"error":"not_found"}')
        try:
            with urlopen(UPSTREAM + "/status", timeout=2) as response:
                payload = json.loads(response.read(65536))
            if payload.get("has_tiles") is False: raise ValueError("tiles")
            self.reply(200, b'{"engine":"GO Iraq","ready":true}')
        except (OSError, ValueError, URLError):
            self.reply(503, b'{"ready":false}')
    def do_POST(self):
        if not authenticated(self.headers.get("Authorization", "")):
            return self.reply(401, b'{"error":"unauthorized"}')
        if self.path not in ("/route", "/sources_to_targets"):
            return self.reply(404, b'{"error":"not_found"}')
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 2 or size > MAX_BODY or self.headers.get("Transfer-Encoding"): raise ValueError()
            payload = validated_payload(json.loads(self.rfile.read(size)), route=self.path == '/route')
            body = json.dumps(payload).encode()
        except (ValueError, OSError):
            return self.reply(400, b'{"error":"invalid_request"}')
        if not SLOTS.acquire(blocking=False):
            return self.reply(429, b'{"error":"busy"}', retry=True)
        started = time.monotonic()
        status = 502
        try:
            req = Request(UPSTREAM + self.path, data=body, headers={"Content-Type":"application/json"})
            with urlopen(req, timeout=18) as response:
                data = response.read(MAX_REPLY + 1)
            if len(data) > MAX_REPLY: raise ValueError()
            result = json.loads(data)
            if self.path == "/route": result = directional_choices(payload, route_choices(result))
            status = 200
            self.reply(status, json.dumps(result).encode())
        except DirectionUnavailable:
            status = 422
            self.reply(status, b'{"error":"direction_unavailable","retry_with_fresh_location":true}')
        except HTTPError as error:
            status = error.code if 400 <= error.code < 600 else 502
            self.reply(status, error.read(MAX_REPLY))
        except (OSError, ValueError, URLError):
            status = 502
            self.reply(status, b'{"error":"routing_unavailable"}')
        finally:
            SLOTS.release()
            print(json.dumps({"event":"routing","status":status,"elapsed_ms":round((time.monotonic()-started)*1000)}), flush=True)

if __name__ == "__main__":
    if len(KEY) < 32: raise SystemExit("GO_ROUTING_KEY must be configured")
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()

