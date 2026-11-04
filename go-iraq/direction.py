"""Verify departure geometry before publishing heading-aware road guidance."""
import math


class DirectionUnavailable(ValueError):
    pass


def decode(shape):
    points = []
    cursor = lat = lon = 0
    while cursor < len(shape):
        deltas = []
        for _ in range(2):
            value = shift = 0
            while True:
                if cursor >= len(shape) or shift > 30:
                    raise ValueError('invalid_shape')
                byte = ord(shape[cursor]) - 63
                cursor += 1
                if not 0 <= byte <= 63:
                    raise ValueError('invalid_shape')
                value |= (byte & 31) << shift
                shift += 5
                if byte < 32:
                    break
            deltas.append(~(value >> 1) if value & 1 else value >> 1)
        lat += deltas[0]
        lon += deltas[1]
        if not -90000000 <= lat <= 90000000 or not -180000000 <= lon <= 180000000:
            raise ValueError('invalid_shape')
        points.append((lat / 1e6, lon / 1e6))
    return points


def distance(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = lat2 - lat1, math.radians(b[1] - a[1])
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(max(0, hav))))


def bearing(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    return math.degrees(math.atan2(math.sin(dlon) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))) % 360


def compatible(trip, origin, heading):
    try:
        leg = trip['legs'][0]
        points = decode(leg['shape'])
        if len(points) < 2:
            return False
        ahead = next((p for p in points[1:] if distance(points[0], p) >= 10), points[-1])
        if distance(points[0], ahead) < 1:
            return False
        angle = abs((bearing(points[0], ahead) - heading + 540) % 360 - 180)
        if angle <= 115:
            return True
        first = next((m for m in leg.get('maneuvers', []) if m.get('type') not in (1, 2, 3)), {})
        index = first.get('begin_shape_index')
        return (first.get('type') in (12, 13) and type(index) is int and 0 <= index < len(points)
            and distance(origin, points[0]) <= 12 and distance(origin, points[index]) <= 12)
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def directional_choices(request, response):
    """Heading is a core preference; never silently publish its opposing fallback.

    Preserve the original destination and provider instructions. An already
    computed compatible alternate may become primary; no geometry is invented.
    """
    start = request['locations'][0]
    if 'heading' not in start or 'trip' not in response:
        return response
    origin = (start['lat'], start['lon'])
    trips = [response['trip']] + [a['trip'] for a in response.get('alternates', [])]
    valid = [trip for trip in trips if compatible(trip, origin, start['heading'])]
    if not valid:
        raise DirectionUnavailable('no_compatible_departure')
    return {**response, 'trip': valid[0], 'alternates': [{'trip': t} for t in valid[1:]]}
