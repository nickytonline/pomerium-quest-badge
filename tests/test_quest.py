import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "badge", "pomerium_quest"))

from quest import EMAIL, KNIGHT_QUOTA, Quest, email_for  # noqa: E402


def citizen():
    quest = Quest()
    quest.sign_in()
    quest.send("SAGE_SPOKE")
    quest.send("CITIZEN_GRANTED")
    quest.sign_in()

    return quest


class Progression(unittest.TestCase):
    def test_signing_in_makes_a_newcomer(self):
        quest = Quest()
        quest.sign_in()
        self.assertEqual(quest.stage, "newcomer")
        self.assertEqual(quest.session["groups"], ())

    def test_granted_citizenship_needs_a_new_sign_in(self):
        quest = Quest()
        quest.sign_in()
        quest.send("SAGE_SPOKE")
        quest.send("CITIZEN_GRANTED")
        self.assertEqual(quest.stage, "granted")
        self.assertEqual(quest.stale(), ["citizens", "your deed"])

        quest.sign_in()
        self.assertEqual(quest.stage, "citizen")
        self.assertEqual(quest.session["groups"], ("citizens",))
        self.assertEqual(quest.session["deed"], "house-1")

    def test_events_out_of_order_do_nothing(self):
        quest = Quest()
        quest.send("CITIZEN_GRANTED")
        quest.send("KNIGHTED")
        self.assertEqual(quest.stage, "anonymous")

    def test_slimes_beaten_early_still_count(self):
        quest = Quest()

        for _ in range(KNIGHT_QUOTA):
            quest.defeat_monster()

        quest.sign_in()
        quest.send("SAGE_SPOKE")
        quest.send("CITIZEN_GRANTED")
        quest.sign_in()
        self.assertEqual(quest.stage, "proven")

    def test_knighted_session_is_stale_until_signing_in_again(self):
        quest = citizen()

        for _ in range(KNIGHT_QUOTA):
            quest.defeat_monster()

        quest.send("KNIGHTED")
        self.assertEqual(quest.stage, "knighted")
        self.assertNotIn("knights", quest.session["groups"])

        quest.sign_in()
        self.assertEqual(quest.stage, "knight")
        self.assertIn("knights", quest.session["groups"])

        quest.send("STEEL_TAKEN")
        self.assertTrue(quest.has_steel())

    def test_scholars_reach_the_session_at_the_next_sign_in(self):
        quest = citizen()
        quest.update(scholar=True)
        self.assertEqual(quest.stale(), ["scholars"])
        quest.sign_in()
        self.assertIn("scholars", quest.session["groups"])


class WhoYouAre(unittest.TestCase):
    def test_the_badge_username_makes_the_address(self):
        self.assertEqual(email_for("Nick Taylor", "nickytonline"), "nickytonline@quest.example")

    def test_a_name_makes_the_address_without_a_username(self):
        self.assertEqual(email_for("Nick", ""), "nick@quest.example")
        self.assertEqual(email_for("Mary Jo O'Neil", ""), "mary.jo.oneil@quest.example")

    def test_nothing_usable_falls_back(self):
        self.assertEqual(email_for("", ""), EMAIL)
        self.assertEqual(email_for("-- ''", ""), EMAIL)

    def test_signing_in_carries_the_players_address(self):
        quest = Quest()
        quest.set_player("Nick")
        quest.sign_in()
        self.assertEqual(quest.session["email"], "nick@quest.example")

    def test_the_player_is_saved(self):
        quest = Quest()
        quest.set_player("Nick Taylor", "nickytonline")
        loaded = Quest.from_save(json.loads(json.dumps(quest.to_save())))
        self.assertEqual((loaded.name, loaded.handle), ("Nick Taylor", "nickytonline"))


class Saving(unittest.TestCase):
    def test_round_trips_through_json(self):
        quest = citizen()
        quest.defeat_monster()
        quest.learn("idp")
        quest.record("ALLOW", "GET", "/zones/town/enter", "you@quest.example")
        restored = Quest.from_save(json.loads(json.dumps(quest.to_save())))

        self.assertEqual(restored.stage, "citizen")
        self.assertEqual(restored.defeated, 1)
        self.assertEqual(restored.session, quest.session)
        self.assertEqual(restored.progress["lessons"], ["idp"])
        self.assertEqual(len(restored.log), 1)

    def test_a_save_it_cannot_read_starts_over(self):
        self.assertEqual(Quest.from_save({"version": 99, "stage": "armed"}).stage, "anonymous")
        self.assertEqual(Quest.from_save(None).stage, "anonymous")


if __name__ == "__main__":
    unittest.main()
