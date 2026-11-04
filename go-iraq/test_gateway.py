import unittest
from unittest.mock import patch
from gateway import route_choices, authenticated, validated_payload
from direction import directional_choices, DirectionUnavailable, compatible, decode
def trip(shape): return {"legs":[{"shape":shape}]}
class Choices(unittest.TestCase):
    def test_no_artificial_alternates(self):
        self.assertEqual(route_choices({"trip":trip("a")})["alternates"], [])
    def test_distinct_four(self):
        result=route_choices({"trip":trip("a"),"alternates":[{"trip":trip(s)} for s in ["a","b","c","d","e"]]})
        self.assertEqual([x["trip"]["legs"][0]["shape"] for x in result["alternates"]], ["b","c","d"])
    def test_errors_preserved(self):
        self.assertEqual(route_choices({"error_code":442}), {"error_code":442})
    def test_non_ascii_authorization_is_rejected_without_crashing(self):
        with patch('gateway.KEY', 'x' * 32):
            self.assertFalse(authenticated('Bearer café'))
            self.assertTrue(authenticated('Bearer ' + 'x' * 32))
            self.assertFalse(authenticated('Bearer ' + 'y' * 32))
    def test_malformed_locations_are_rejected(self):
        for locations in [None, {}, 'xx', [], [{}], [{}] * 7]:
            with self.assertRaises(ValueError):
                validated_payload({'locations': locations}, route=True)
    def test_alternative_bounds_and_multistop(self):
        for count in [-1, 4, True, 1.5, '3']:
            with self.assertRaises(ValueError):
                validated_payload({'locations': [{}, {}], 'alternates': count}, route=True)
        self.assertEqual(validated_payload({'locations': [{}, {}]}, route=True)['alternates'], 3)
        self.assertEqual(validated_payload({'locations': [{}, {}, {}], 'alternates': 3}, route=True)['alternates'], 0)
def encoded(points):
    result = ''
    previous = (0, 0)
    for point in points:
        current = tuple(round(v * 1e6) for v in point)
        for value, old in zip(current, previous):
            delta = value - old
            number = ~(delta << 1) if delta < 0 else delta << 1
            while number >= 32:
                result += chr((32 | (number & 31)) + 63)
                number >>= 5
            result += chr(number + 63)
        previous = current
    return result


class Direction(unittest.TestCase):
    request = {'locations': [{'lat': 0, 'lon': 0, 'heading': 90}, {'lat': 0, 'lon': .01}]}
    def path(self, east=True, maneuvers=None):
        return {'legs': [{'shape': encoded([(0, 0), (0, .0002 if east else -.0002), (0, .001 if east else -.001)]), 'maneuvers': maneuvers or []}]}
    def test_promotes_computed_compatible_alternate(self):
        valid = self.path()
        result = directional_choices(self.request, {'trip': self.path(False), 'alternates': [{'trip': valid}]})
        self.assertIs(result['trip'], valid)
        self.assertEqual(result['alternates'], [])
    def test_rejects_silent_opposing_fallback(self):
        with self.assertRaises(DirectionUnavailable):
            directional_choices(self.request, {'trip': self.path(False)})
    def test_explicit_immediate_turnaround_only(self):
        for kind in (12, 13):
            path = self.path(False, [{'type': 1}, {'type': kind, 'begin_shape_index': 0}])
            self.assertTrue(compatible(path, (0, 0), 90))
            self.assertFalse(compatible(path, (0, .0002), 90))
            path['legs'][0]['maneuvers'][1]['begin_shape_index'] = 1
            self.assertFalse(compatible(path, (0, 0), 90))
        path = self.path(False, [{'type': 10, 'begin_shape_index': 0}, {'type': 12, 'begin_shape_index': 0}])
        self.assertFalse(compatible(path, (0, 0), 90))
    def test_no_heading_preserves_normal_route(self):
        response = {'trip': self.path(False)}
        self.assertIs(directional_choices({'locations': [{}, {}]}, response), response)
    def test_invalid_or_truncated_shapes_do_not_publish(self):
        for shape in ['_', '~~~~~~~', '\\x00', '']:
            self.assertFalse(compatible(trip(shape), (0, 0), 90))
        points = [(33.311986, 44.385596), (33.311885, 44.385134)]
        self.assertEqual(decode(encoded(points)), points)
    def test_invalid_heading_is_input_error(self):
        for heading in [True, '90', float('nan'), float('inf'), -1, 361]:
            with self.assertRaises(ValueError):
                validated_payload({'locations': [{'lat': 0, 'lon': 0, 'heading': heading}, {}]}, route=True)

if __name__ == "__main__": unittest.main()

