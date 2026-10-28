import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "badge", "pomerium_quest"))

import data  # noqa: E402
import ppl  # noqa: E402


def load_fixtures():
    with open(os.path.join(HERE, "fixtures", "decisions.json")) as file:
        return json.load(file)


class MatchesTheBrowserGame(unittest.TestCase):
    """Every decision the browser game's evaluator made, made again by the badge's port."""

    def test_every_decision(self):
        fixtures = load_fixtures()
        self.assertGreater(len(fixtures), 100)

        for case in fixtures:
            who = ppl.identity(**case["id"])
            allow, lines = ppl.decide(case["policy"], who, case["method"], case["whose"])
            label = "%s as %s %s" % (case["name"], case["id"]["email"] or "anonymous", case["method"])

            with self.subTest(label):
                self.assertEqual(allow, case["allow"])
                self.assertEqual(lines, case["lines"])


class PolicyYaml(unittest.TestCase):
    def test_matches_the_route_config_on_each_sign(self):
        for zone in data.ZONES:
            with self.subTest(zone["id"]):
                self.assertEqual(ppl.policy_yaml(zone["policy"], 4), list(data.ROUTE_YAML[zone["id"]][5:]))


class ClaimValues(unittest.TestCase):
    def test_deed_is_always_quoted(self):
        self.assertEqual(ppl.claim_value("deed", "house-1"), '"house-1"')

    def test_values_that_look_typed_are_quoted(self):
        for value in ("123", "-x", "true", "No", "~"):
            self.assertEqual(ppl.claim_value("groups", value), '"%s"' % value)

    def test_plain_names_are_not(self):
        self.assertEqual(ppl.claim_value("groups", "knights"), "knights")


if __name__ == "__main__":
    unittest.main()
