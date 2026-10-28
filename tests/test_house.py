import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "badge", "pomerium_quest"))
sys.path.insert(0, os.path.dirname(__file__))

import house  # noqa: E402
from test_story import FakeGame  # noqa: E402


def owner():
    g = FakeGame()
    g.quest.sign_in()
    g.quest.send("SAGE_SPOKE")
    g.quest.send("CITIZEN_GRANTED")
    g.quest.sign_in()

    return g


class Letters(unittest.TestCase):
    def test_exactly_one_choice_solves_each_letter(self):
        session = owner().quest.session

        for letter_id in house.LETTER_ORDER:
            letter = house.LETTERS[letter_id]
            right = [
                label
                for label, rules in house.OPTIONS[letter_id]
                if not house.solves(letter, rules, session)
                and (not letter.get("needsDeny") or any(rule["action"] == "deny" for rule in rules))
            ]

            with self.subTest(letter_id):
                self.assertEqual(len(right), 1, right)

    def test_answering_every_letter(self):
        g = owner()
        picks = {"slimes": 0, "bread": 1, "guild": 1, "baker": 2, "window": 0}
        g.pick = lambda title, options, chosen: chosen(picks[house.stage(g.quest)])

        for _ in house.LETTER_ORDER:
            house.use_desk(g)

        self.assertEqual(house.stage(g.quest), "done")
        self.assertIn("denyWins", g.quest.progress["lessons"])

    def test_a_wrong_choice_says_who_came_out_wrong(self):
        g = owner()
        g.pick = lambda title, options, chosen: chosen(1)
        house.use_desk(g)
        self.assertEqual(house.stage(g.quest), "slimes")
        self.assertIn("A slime bot got in", g.pages[-1]["text"])


class Door(unittest.TestCase):
    def test_a_new_house_is_public(self):
        g = owner()
        self.assertTrue(house.knock(g.quest, "slime"))
        self.assertIn("  allow_public_unauthenticated_access: true", house.route_yaml(g.quest))

    def test_the_deed_lets_the_owner_in(self):
        g = owner()
        g.quest.update(house_rules=[])
        self.assertTrue(house.knock(g.quest, "you"))
        self.assertFalse(house.knock(g.quest, "slime"))
        self.assertFalse(house.knock(g.quest, "traveler"))


if __name__ == "__main__":
    unittest.main()
