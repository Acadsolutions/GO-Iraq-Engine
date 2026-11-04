import unittest
from unittest.mock import patch
from gateway import route_choices, authenticated, validated_payload
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
if __name__ == "__main__": unittest.main()

