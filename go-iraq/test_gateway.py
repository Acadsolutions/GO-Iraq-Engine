import unittest
from gateway import route_choices
def trip(shape): return {"legs":[{"shape":shape}]}
class Choices(unittest.TestCase):
    def test_no_artificial_alternates(self):
        self.assertEqual(route_choices({"trip":trip("a")})["alternates"], [])
    def test_distinct_four(self):
        result=route_choices({"trip":trip("a"),"alternates":[{"trip":trip(s)} for s in ["a","b","c","d","e"]]})
        self.assertEqual([x["trip"]["legs"][0]["shape"] for x in result["alternates"]], ["b","c","d"])
    def test_errors_preserved(self):
        self.assertEqual(route_choices({"error_code":442}), {"error_code":442})
if __name__ == "__main__": unittest.main()
