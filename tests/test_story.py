import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "badge", "pomerium_quest"))

import story  # noqa: E402
from quest import KNIGHT_QUOTA, Quest  # noqa: E402


class FakeGame:
    """Stands in for the game: dialogs close straight away, and choices pick `choice`."""

    def __init__(self, choice=1):
        self.quest = Quest()
        self.choice = choice
        self.pages = []
        self.denials = []
        self.toasts = []
        self.ended = None
        self.oracle_shown = False

    def say(self, pages, then=None):
        self.pages.extend(pages)

        if then:
            then()

    def ask(self, pages, choices):
        self.pages.extend(pages)
        choices[self.choice][1]()

    def deny(self, view, then=None):
        self.denials.append(view)

        if then:
            then()

    def toast(self, text, tone="info"):
        self.toasts.append(text)

    def oracle_beside(self, shown):
        self.oracle_shown = shown

    def finale(self):
        self.ended = "finale"

    def phished(self):
        self.ended = "phished"


class PlaysThrough(unittest.TestCase):
    def test_the_whole_quest(self):
        g = FakeGame()

        self.assertEqual(story.enter_gate(g, "fields"), "signin")
        self.assertEqual(g.denials[-1]["status"], 401)

        story.talk(g, "sage")
        story.talk(g, "oracle")
        self.assertEqual(g.quest.stage, "newcomer")
        self.assertEqual(story.enter_gate(g, "fields"), "allow")
        self.assertEqual(story.enter_gate(g, "town"), "deny")

        story.talk(g, "sage")
        story.talk(g, "oracle")
        self.assertEqual(g.quest.stage, "citizen")
        self.assertEqual(g.quest.session["deed"], "house-1")
        self.assertEqual(story.enter_gate(g, "town"), "allow")
        self.assertEqual(story.enter_gate(g, "armory"), "deny")

        for _ in range(KNIGHT_QUOTA):
            g.quest.defeat_monster()

        story.talk(g, "captain")
        self.assertEqual(g.quest.stage, "knight")
        self.assertFalse(g.oracle_shown)
        self.assertEqual(story.enter_gate(g, "armory"), "allow")
        self.assertTrue(story.open_chest(g))
        self.assertTrue(g.quest.has_steel())

        self.assertEqual(story.enter_gate(g, "library"), "allow")
        self.assertEqual(story.enter_gate(g, "scriptorium"), "deny")
        self.assertEqual(g.denials[-1]["story_title"], "Scribes only")

        for shelf in (30, 31, 32):
            story.read_book(g, shelf)

        story.talk(g, "librarian")
        self.assertIn("scholars", g.quest.session["groups"])

        self.assertEqual(story.enter_gate(g, "keep"), "allow")
        self.assertEqual(g.ended, "finale")
        self.assertIn("allOf", g.quest.progress["lessons"])

    def test_the_keep_names_what_is_missing(self):
        g = FakeGame()
        story.talk(g, "oracle")
        story.talk(g, "sage")
        story.talk(g, "oracle")
        story.enter_gate(g, "keep")
        self.assertIn("a knight", g.denials[-1]["story"])
        self.assertIn("a scholar", g.denials[-1]["story"])

    def test_signing_in_with_a_phish_ends_the_game(self):
        g = FakeGame(choice=0)
        story.meet_phish(g, lambda: None)
        self.assertEqual(g.ended, "phished")

    def test_refusing_a_phish_turns_it_away(self):
        g = FakeGame(choice=1)
        turned = []
        story.meet_phish(g, lambda: turned.append(True))
        self.assertEqual(turned, [True])
        self.assertIsNone(g.ended)


class Claims(unittest.TestCase):
    def test_claims_read_like_json(self):
        import json

        g = FakeGame()
        story.talk(g, "oracle")
        story.talk(g, "sage")
        story.talk(g, "oracle")
        claims = json.loads("\n".join(story.claims_code(g.quest.session)))
        self.assertEqual(claims["groups"], ["citizens"])
        self.assertEqual(claims["deed"], "house-1")


if __name__ == "__main__":
    unittest.main()
