"""Run inside the built image, with networking disabled except container loopback.

Public road fixture points, never a user's live location. This measures routing
requests in CI, not end-to-end phone latency or physical driving acceptance.
"""
import json
import math
import os
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8080'
KEY = os.environ['GO_ROUTING_KEY']


def call(path, body=None, auth=True):
    headers = {'Content-Type': 'application/json'}
    if auth:
        headers['Authorization'] = 'Bearer ' + KEY
    request = Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def decode(shape):
    values = []
    index = lat = lon = 0
    while index < len(shape):
        delta = []
        for _ in range(2):
            value = shift = 0
            while True:
                byte = ord(shape[index]) - 63
                index += 1
                value |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            delta.append(~(value >> 1) if value & 1 else value >> 1)
        lat += delta[0]
        lon += delta[1]
        values.append((lat / 1e6, lon / 1e6))
    return values


def distance(a, b):
    lat1, lat2 = map(math.radians, [a[0], b[0]])
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    return 12742000 * math.asin(min(1, math.sqrt(math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)))


def bearing(a, b):
    lat1, lat2 = map(math.radians, [a[0], b[0]])
    dlon = math.radians(b[1] - a[1])
    return math.degrees(math.atan2(math.sin(dlon) * math.cos(lat2), math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))) % 360


def route(origin, goal, heading=None):
    start = {'lat': origin[0], 'lon': origin[1]}
    if heading is not None:
        start.update(heading=round(heading) % 360, heading_tolerance=60)
    payload = {'locations': [start, {'lat': goal[0], 'lon': goal[1]}], 'costing': 'auto', 'alternates': 3, 'units': 'kilometers', 'language': 'ar'}
    started = time.perf_counter()
    status, response = call('/route', payload)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    assert status == 200 and response['trip']['status'] == 0, (status, response)
    trips = [response['trip']] + [a['trip'] for a in response.get('alternates', [])]
    assert 1 <= len(trips) <= 4
    geometries = [tuple(leg['shape'] for leg in trip['legs']) for trip in trips]
    assert len(set(geometries)) == len(geometries)
    for trip in trips:
        assert distance(decode(trip['legs'][-1]['shape'])[-1], goal) < 200, 'destination changed'
    return response, elapsed


for attempt in range(90):
    try:
        if call('/health', auth=False) == (200, {'engine': 'GO Iraq', 'ready': True}):
            break
    except (URLError, OSError):
        pass
    time.sleep(1)
else:
    raise AssertionError('engine did not become ready')

assert call('/route', {}, auth=False)[0] == 401
assert call('/route', {'alternates': 4, 'locations': []})[0] == 400
reports = []
failures = []
for name, origin, goal in [
    ('Baghdad', (33.327782, 44.408362), (33.312113, 44.363983)),
    ('Nijkerk', (52.2221112, 5.4885404), (52.2200991, 5.4870599)),
]:
    response, cold = route(origin, goal)
    points = decode(response['trip']['legs'][0]['shape'])
    middle = max(1, min(len(points) - 2, len(points) // 2))
    incompatible_heading = bearing(points[middle], points[middle - 1])
    fallback_status, fallback = call('/route', {'locations': [
        {'lat': points[middle][0], 'lon': points[middle][1], 'heading': round(incompatible_heading) % 360, 'heading_tolerance': 60},
        {'lat': goal[0], 'lon': goal[1]}], 'costing': 'auto', 'alternates': 3})
    if fallback_status == 422:
        assert fallback.get('error') == 'direction_unavailable' and fallback.get('retry_with_fresh_location') is True
    else:
        assert fallback_status == 200, (fallback_status, fallback)
        candidate = fallback['trip']['legs'][0]
        candidate_points = decode(candidate['shape'])
        candidate_ahead = next((p for p in candidate_points[1:] if distance(candidate_points[0], p) >= 10), candidate_points[-1])
        candidate_angle = abs((bearing(candidate_points[0], candidate_ahead) - incompatible_heading + 540) % 360 - 180)
        candidate_first = next((m for m in candidate.get('maneuvers', []) if m.get('type') not in (1, 2, 3)), {})
        candidate_index = candidate_first.get('begin_shape_index', -1)
        candidate_turn = candidate_first.get('type') in (12, 13) and 0 <= candidate_index < len(candidate_points) and distance(points[middle], candidate_points[0]) <= 12 and distance(points[middle], candidate_points[candidate_index]) <= 12
        assert candidate_angle <= 115 or candidate_turn, (name, 'silent opposing fallback was published', candidate_angle)
    # Obtain a legal return path, rather than reversing on a one-way carriageway.
    returning, _ = route(goal, origin)
    back_points = decode(returning['trip']['legs'][0]['shape'])
    back_index = max(0, min(len(back_points) - 2, len(back_points) // 2))
    reverse_origin = tuple((a + b) / 2 for a, b in zip(back_points[back_index], back_points[back_index + 1]))
    reverse_heading = bearing(back_points[back_index], back_points[back_index + 1])
    reverse, reroute_ms = route(reverse_origin, goal, reverse_heading)
    reverse_points = decode(reverse['trip']['legs'][0]['shape'])
    ahead = next((p for p in reverse_points[1:] if distance(reverse_points[0], p) >= 10), reverse_points[-1])
    angle = abs((bearing(reverse_points[0], ahead) - reverse_heading + 540) % 360 - 180)
    # A provider may explicitly choose a nearby legal turn-around. It must be
    # represented as a maneuver, not inferred from an old forward instruction.
    maneuvers = reverse['trip']['legs'][0].get('maneuvers', [])
    first_turn = next((m for m in maneuvers if m.get('type') not in (1, 2, 3)), {})
    turn_index = first_turn.get('begin_shape_index', -1)
    early_turn = first_turn.get('type') in (12, 13) and 0 <= turn_index < len(reverse_points) and distance(reverse_origin, reverse_points[0]) <= 12 and distance(reverse_origin, reverse_points[turn_index]) <= 12
    if not (angle <= 115 or early_turn):
        print(json.dumps({'failure_region': name, 'public_fixture_origin': points[middle],
            'requested_heading': reverse_heading, 'departure_angle': angle,
            'response_locations': reverse['trip'].get('locations'),
            'initial_points': reverse_points[:8], 'initial_maneuvers': maneuvers[:4],
            'alternates': [a['trip']['legs'][0].get('maneuvers', [])[:3] for a in reverse.get('alternates', [])]}, ensure_ascii=False), flush=True)
    if not (angle <= 115 or early_turn): failures.append((name, 'reverse request produced opposing geometry', angle))
    warm = [route(origin, goal)[1] for _ in range(5)]
    reports.append({'region': name, 'choices': 1 + len(response.get('alternates', [])), 'cold_ms': cold,
                    'reverse_ms': reroute_ms, 'warm_median_ms': statistics.median(warm),
                    'warm_max_ms': max(warm), 'reverse_departure_error_degrees': round(angle, 1),
                    'destination_preserved': True, 'opposing_fallback_status': fallback_status})
print(json.dumps({'environment': 'GitHub CI, 1 CPU / 1 GiB, container loopback only',
                  'physical_device': 'not_run', 'routing': reports}, indent=2))
assert not failures, failures
