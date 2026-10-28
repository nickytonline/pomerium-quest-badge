import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "badge", "pomerium_quest"))
sys.path.insert(0, os.path.dirname(__file__))

import data  # noqa: E402
import house  # noqa: E402
import household  # noqa: E402
from test_house import owner  # noqa: E402


class Body:
    """Just enough of the game's Sprite: a tile, and a glide that takes `ms` to finish."""

    def __init__(self, x, y, npc_id=None):
        self.x, self.y = x, y
        self.from_x, self.from_y = x, y
        self.moved_at = -10000
        self.ms = 1
        self.npc_id = npc_id
        self.home = "fields"
        self.held = False
        self.lift = 0

    def move(self, x, y, now, ms=140):
        self.from_x, self.from_y = self.x, self.y
        self.x, self.y = x, y
        self.moved_at = now
        self.ms = ms

    def moving(self, now):
        return now - self.moved_at < self.ms


class World:
    """The kingdom without the drawing: the map, its townsfolk, and a clock to run the house by."""

    def __init__(self, quest):
        self.quest = quest
        self.now = 0
        self.tiles = [bytearray(row) for row in data.MAP]
        self.npcs = [Body(npc["x"], npc["y"], npc["npcId"]) for npc in data.NPCS]
        self.monsters = []
        self.guards = []
        # Far from the house, in the Library Quarter, so they're never in the way.
        self.player = Body(30, 25)
        self.jobs = []
        self.toasts = []
        self.bites = 0
        self.household = household.Household(self)

    def tile(self, x, y):
        return self.tiles[y][x] if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[0]) else data.TILE["tree"]

    def set_tile(self, x, y, tile):
        self.tiles[y][x] = tile

    def occupied(self, x, y):
        bodies = self.npcs + self.monsters + ([self.household.guard] if self.household.guard else [])

        return any((body.x, body.y) == (x, y) for body in bodies)

    def toast(self, text, tone="info"):
        self.toasts.append(text)

    def start(self, job):
        self.jobs.append([job, self.now])

    def make_sprite(self, x, y, frame):
        return Body(x, y)

    def teleport(self, body, to):
        body.x, body.y = to
        body.from_x, body.from_y = to
        body.moved_at = -10000

    def can_see(self, x, y):
        return True

    def take_bite(self, table, mouth, lift_ms, chew_ms):
        self.bites += 1

    def drop_crumb(self, at):
        pass

    def run(self, ms, until=None):
        """Runs the house in 30 ms frames, like the badge, until `until` holds or `ms` have passed."""
        end = self.now + ms

        while self.now < end:
            self.now += 30

            for job in list(self.jobs):
                if self.now >= job[1]:
                    try:
                        job[1] = self.now + (next(job[0]) or 0)
                    except StopIteration:
                        self.jobs.remove(job)

            self.household.tick(self.now, False)

            if until and until():
                return True

        return False


def at(body, p):
    return (body.x, body.y) == p


class TheTraveler(unittest.TestCase):
    def test_eats_the_bread_in_an_open_house_then_leaves(self):
        world = World(owner().quest)
        life = world.household
        self.assertEqual(life.bread, household.WHOLE_LOAF)

        self.assertTrue(world.run(120000, lambda: life.plan == "eat"), "the traveler never sat down to eat")
        self.assertTrue(at(life.traveler, household.SEAT) or household.at_table((life.traveler.x, life.traveler.y)))
        self.assertTrue(world.run(60000, lambda: life.plan == "roam"), "the traveler never left")
        self.assertEqual(life.bread, 0)
        self.assertGreater(world.bites, 0)
        self.assertFalse(household.in_house(life.traveler.x, life.traveler.y))
        self.assertEqual(world.tile(*household.TABLE), data.TILE["tableCrumbs"])

    def test_the_door_shuts_once_nobody_is_in_it(self):
        world = World(owner().quest)
        world.run(30)
        self.assertEqual(world.tile(*household.DOOR), data.TILE["doorClosed"])

        world.player.move(household.DOOR[0], household.DOOR[1], world.now)
        world.run(30)
        self.assertEqual(world.tile(*household.DOOR), data.TILE["door"])

    def test_a_fresh_loaf_turns_up_after_the_last_is_eaten(self):
        world = World(owner().quest)
        world.household.bread = 0
        world.run(household.NEW_LOAF_MS + 100)
        self.assertEqual(world.household.bread, household.WHOLE_LOAF)


class NewDoorRules(unittest.TestCase):
    def test_a_guard_shows_out_whoever_the_rules_turn_away(self):
        world = World(owner().quest)
        life = world.household
        world.run(120000, lambda: life.plan == "eat")

        # Only citizens now; the traveler isn't one.
        world.quest.update(house_rules=[house.rule("allow", "or", house.group("citizens"))])
        life.rules_saved()
        world.run(30)
        self.assertEqual(life.plan, "escorted")
        self.assertTrue(world.run(60000, lambda: not world.jobs), "the guard never finished")

        self.assertEqual(life.plan, "roam")
        self.assertFalse(household.in_house(life.traveler.x, life.traveler.y))
        self.assertIsNotNone(life.guard)
        self.assertFalse(household.in_house(life.guard.x, life.guard.y))

    def test_the_captain_visits_once_the_door_lets_knights_in(self):
        world = World(owner().quest)
        life = world.household
        world.quest.update(house_rules=[house.rule("allow", "or", house.group("knights"))])
        life.rules_saved()

        self.assertTrue(world.run(30000, lambda: life.captain_at == "inside"), "the Captain never came in")
        self.assertTrue(at(life.captain, household.CAPTAIN_SPOT))

        # Rules that turn knights away again: the guard shows the Captain out, and they go home.
        world.quest.update(house_rules=[])
        life.rules_saved()
        self.assertTrue(world.run(60000, lambda: life.captain_at == "guild"))
        self.assertTrue(at(life.captain, life.captain_home))


if __name__ == "__main__":
    unittest.main()
