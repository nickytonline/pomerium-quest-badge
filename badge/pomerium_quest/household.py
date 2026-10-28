# Life around the player's house: the door that shuts behind whoever walks through it, the loaf on the
# table, the traveler who roams the fields and knocks to get at it, the guard who shows out anyone new door
# rules turn away, and the Captain, who drops by once the door lets knights in. A port of the house half of
# the browser game's scene.ts.
#
# The browser runs the guard's and the Captain's walks as async functions. Here each is a generator the game
# steps every frame (see Game.run_jobs): it yields how many milliseconds to wait before its next step.

import random

import data
import house

TILE = data.TILE
HOUSE = data.HOUSE
WALKABLE = set(data.WALKABLE)

DOOR = (HOUSE["door"]["x"], HOUSE["door"]["y"])
DOORSTEP = (HOUSE["doorstep"]["x"], HOUSE["doorstep"]["y"])
SEAT = (HOUSE["seat"]["x"], HOUSE["seat"]["y"])
TABLE = (HOUSE["table"]["x"], HOUSE["table"]["y"])
DESK = (HOUSE["desk"]["x"], HOUSE["desk"]["y"])

#: Where a guard leaves an intruder: the path just past the doorstep.
OUTSIDE = (DOORSTEP[0] + 1, DOORSTEP[1])

#: Where the Captain stands while visiting, just inside the door, to say hello.
CAPTAIN_SPOT = (5, 11)

#: How long the Captain stays when they drop by.
CAPTAIN_STAYS_MS = 40000

#: The traveler's pace: a step, a pause between roaming steps, and how often they come to the door. The first
#: visit comes soon after the game starts; after that, one a minute.
STEP_MS = 300
ROAM_MS = 900
FIRST_VISIT_MS = 15000
VISIT_MS = 60000
BITE_MS = 1200
#: Bites to finish each quarter of the loaf.
BITES_PER_PIECE = 2
#: How long the traveler looks at an empty table before giving up.
EMPTY_TABLE_MS = 1500
#: How many times a blocked step is tried again before the traveler finds another way.
PATIENCE = 4

#: The table as the loaf goes, by how many quarters are left.
LOAF = (TILE["tableCrumbs"], TILE["tableHeel"], TILE["tableHalf"], TILE["tableBitten"], TILE["tableBread"])
WHOLE_LOAF = len(LOAF) - 1

#: How long after the last of the loaf is eaten until a fresh one is on the table.
NEW_LOAF_MS = 90000

#: Most bites go down whole; this share of them drops a crumb.
CRUMB_CHANCE = 0.35

#: A bite goes up from the table to the traveler's mouth, and is chewed there.
MORSEL_LIFT_MS = 200
MORSEL_CHEW_MS = 450

FIELDS = (1, 1, 15, 16)
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def in_house(x, y):
    inside = HOUSE["inside"]

    return inside["x0"] <= x <= inside["x1"] and inside["y0"] <= y <= inside["y1"]


def in_fields(x, y):
    return FIELDS[0] <= x <= FIELDS[2] and FIELDS[1] <= y <= FIELDS[3]


def at_table(p):
    """Where the traveler eats: their seat above the table, or failing that any tile beside it."""
    return in_house(p[0], p[1]) and (p == SEAT or abs(p[0] - TABLE[0]) + abs(p[1] - TABLE[1]) == 1)


def loaf_for(stage):
    """A new game's loaf is whole, unless the bread letter has already said the traveler ate it."""
    return WHOLE_LOAF if stage in ("unowned", "slimes") else 0


class Intruder:
    """Someone the door no longer lets in, and what happens to them once they're outside."""

    def __init__(self, body, name, pronoun, release):
        self.body = body
        self.name = name
        self.pronoun = pronoun
        self.release = release


class Household:
    def __init__(self, game):
        self.g = game
        self.traveler = next(npc for npc in game.npcs if npc.npc_id == "traveler")
        self.captain = next(npc for npc in game.npcs if npc.npc_id == "captain")
        self.captain_home = (self.captain.x, self.captain.y)
        # The traveler's plan: roam, visit (walk to the doorstep), knock, enter, eat, leave or escorted.
        self.plan = "roam"
        self.path = []
        self.next_move = 0
        self.next_visit = None
        self.next_bite = 0
        self.bites = 0
        self.blocked = 0
        self.chew_until = 0
        # The guard who shows unwelcome visitors out, and waits by the nearest gate between times.
        self.guard = None
        self.escorting = False
        self.recheck_again = False
        # The Captain: at the guild, visiting (on the way in), inside, or being shown out.
        self.captain_at = "guild"
        self.captain_was_welcome = self.own_rules_welcome("captain")
        self.stage = house.stage(game.quest)
        self.bread = loaf_for(self.stage)
        self.new_loaf_at = None

    # The house as its story stands

    def dress(self):
        """Locked until the deed, then shut unless someone is in the doorway; the loaf; a letter on the desk."""
        g = self.g
        owned = self.stage != "unowned"
        door = TILE["doorLocked"]

        if owned:
            door = TILE["door"] if self.in_doorway() else TILE["doorClosed"]

        letter = owned and house.current_letter(g.quest)[1]
        tiles = ((DOOR, door), (TABLE, LOAF[self.bread]), (DESK, TILE["deskLetter"] if letter else TILE["desk"]))

        for (x, y), tile in tiles:
            if g.tile(x, y) != tile:
                g.set_tile(x, y, tile)

    def in_doorway(self):
        """Whether anyone stands in the doorway, or is still stepping into or out of it."""
        now = self.g.now
        bodies = [self.g.player, self.traveler, self.captain] + self.g.monsters

        if self.guard:
            bodies.append(self.guard)

        for body in bodies:
            if (body.x, body.y) == DOOR or (body.moving(now) and (body.from_x, body.from_y) == DOOR):
                return True

        return False

    def own_rules_welcome(self, caller):
        """Whether door rules of the player's own let a visitor in. Asked without knocking, so nothing goes in
        the access log."""
        door = house.policy(self.g.quest)

        return door is not None and house.allows(door, house.identity_of(self.g.quest, caller), "GET")

    def tick(self, now, paused):
        stage = house.stage(self.g.quest)

        if stage != self.stage:
            # The bread letter says the traveler ate the loaf, so it's gone when the letter arrives.
            if stage == "bread":
                self.bread = 0

            self.stage = stage

        if not paused:
            self.update_traveler(now)
            self.bake_bread(now)

        self.chew(now)
        self.dress()

    def near(self, p, reach=6):
        player = self.g.player

        return abs(player.x - p[0]) + abs(player.y - p[1]) <= reach

    # The traveler

    def update_traveler(self, now):
        traveler = self.traveler

        if traveler.moving(now) or self.plan in ("knock", "escorted"):
            return

        if self.next_visit is None:
            self.next_visit = now + FIRST_VISIT_MS

        if self.plan == "eat":
            self.eat_bread(now)

            return

        if now < self.next_move:
            return

        self.next_move = now + (int(ROAM_MS * (1 + random.random())) if self.plan == "roam" else 0)

        if self.plan == "roam" and now >= self.next_visit and self.stage != "unowned":
            self.next_visit = now + VISIT_MS
            self.set_plan("visit", self.path_for(traveler, lambda p: p == DOORSTEP))

        if self.plan == "roam":
            self.roam()

            return

        if not self.path:
            self.arrived(now)

            return

        step = self.path[0]

        if not self.can_enter(step):
            self.blocked_by(now)

            return

        self.path.pop(0)
        self.blocked = 0
        self.step(traveler, step)

    def set_plan(self, plan, path=None):
        self.plan = plan
        self.path = path or []
        self.blocked = 0

    def roam(self):
        """A random step around the fields, staying out of the house and the water."""
        traveler = self.traveler
        dx, dy = random.choice(STEPS)
        x, y = traveler.x + dx, traveler.y + dy

        if in_fields(x, y) and not in_house(x, y) and self.g.tile(x, y) in WALKABLE and self.can_enter((x, y)):
            self.step(traveler, (x, y))

    def blocked_by(self, now):
        """Something is in the way: wait a moment, then look for another way round."""
        self.next_move = now + 500
        self.blocked += 1
        goal = self.path[-1] if self.path else None

        if self.blocked < PATIENCE or not goal:
            return

        self.blocked = 0
        through_door = self.plan != "visit"
        reached = at_table if self.plan == "enter" else (lambda p: p == goal)
        around = self.path_for(self.traveler, reached, through_door, True)

        if around:
            self.path = around
        # Nowhere to sit: they leave rather than stand in the player's way.
        elif self.plan == "enter":
            self.set_plan("leave", self.path_for(self.traveler, lambda p: p == DOORSTEP, through_door))
        elif self.plan == "visit":
            self.set_plan("roam")

    def arrived(self, now):
        if self.plan == "visit":
            self.knocks()
        elif self.plan == "enter":
            self.set_plan("eat")
            self.bites = 0
            self.next_bite = now + (0 if self.bread > 0 else EMPTY_TABLE_MS)
        elif self.plan == "leave":
            self.set_plan("roam")

    def knocks(self):
        """On the doorstep, the traveler knocks, and the door's rules decide whether they come in."""
        if house.knock(self.g.quest, "traveler"):
            self.set_plan("enter", self.path_for(self.traveler, lambda p: p == SEAT, True))

            return

        self.set_plan("roam")

        if self.near(DOOR):
            self.g.toast(
                "The traveler tries your door. No rule matches them, so Pomerium says no, and they wander off.",
                "allow",
            )

    def eat_bread(self, now):
        """At the table, a bite every so often; the loaf shrinks every few bites, and once it's gone they leave."""
        if now < self.next_bite:
            return

        traveler = self.traveler

        if self.bread == 0:
            self.set_plan("leave", self.path_for(traveler, lambda p: p == DOORSTEP, True))

            return

        self.next_bite = now + int(BITE_MS * (0.8 + random.random() * 0.4))
        self.bites += 1

        if self.bites % BITES_PER_PIECE == 0:
            self.bread -= 1

        if not self.g.can_see(traveler.x, traveler.y):
            return

        self.g.take_bite(TABLE, (traveler.x, traveler.y), MORSEL_LIFT_MS, MORSEL_CHEW_MS)
        self.chew_until = now + MORSEL_LIFT_MS + MORSEL_CHEW_MS

        if random.random() < CRUMB_CHANCE:
            self.g.drop_crumb((traveler.x, traveler.y))

    def chew(self, now):
        """Chewing, the traveler bobs twice."""
        left = self.chew_until - now
        chewing = self.plan == "eat" and 0 < left <= MORSEL_CHEW_MS
        self.traveler.lift = 1 if chewing and (left * 4 // MORSEL_CHEW_MS) % 2 else 0

    def bake_bread(self, now):
        """Once the loaf is gone, a fresh one turns up on the table a while later."""
        if self.bread > 0 or self.stage == "unowned":
            self.new_loaf_at = None

            return

        if self.new_loaf_at is None:
            self.new_loaf_at = now + NEW_LOAF_MS

        if now < self.new_loaf_at:
            return

        self.bread = WHOLE_LOAF

        if in_house(self.g.player.x, self.g.player.y):
            self.g.toast("A fresh loaf of bread is on your table.")

    def step(self, body, to):
        body.move(to[0], to[1], self.g.now, STEP_MS)

    def can_enter(self, p):
        """A free tile: no one there, and the player isn't on it or stepping onto it."""
        player = self.g.player

        return not self.g.occupied(p[0], p[1]) and p != (player.x, player.y)

    def path_for(self, start, goal, through_door=False, avoid=False):
        """The shortest walk around the fields to a tile `goal` accepts, or none. Only on the way in, once the
        door has let them, or back out, does anyone go through the door."""
        g = self.g
        origin = (start.x, start.y) if hasattr(start, "x") else start

        def passable(p):
            tile = g.tile(p[0], p[1])
            door = through_door and tile in (TILE["door"], TILE["doorClosed"])

            return in_fields(p[0], p[1]) and (tile in WALKABLE or door) and (not avoid or self.can_enter(p))

        came_from = {origin: None}
        queue = [origin]
        head = 0

        while head < len(queue):
            here = queue[head]
            head += 1

            if goal(here):
                path = []

                while here != origin:
                    path.insert(0, here)
                    here = came_from[here]

                return path

            for dx, dy in STEPS:
                nxt = (here[0] + dx, here[1] + dy)

                if nxt not in came_from and passable(nxt):
                    came_from[nxt] = here
                    queue.append(nxt)

        return []

    # When the door rules change

    def rules_saved(self):
        """New door rules: the guard checks everyone in the house and shows out whoever the door turns away.
        Rules that change mid-check get a check of their own."""
        if self.escorting:
            self.recheck_again = True

            return

        self.escorting = True
        self.g.start(self.recheck())

    def recheck(self):
        while True:
            self.recheck_again = False
            yield from self.clear_house()

            if not self.recheck_again:
                break

        self.escorting = False

    def clear_house(self):
        """Knocks as whoever is inside, and the guard shows out anyone the door refuses."""
        g = self.g
        quest = g.quest
        intruders = []
        slimes = [monster for monster in g.monsters if monster.home == "house"]

        if slimes and not house.knock(quest, "slime"):
            for slime in slimes:
                # Stay put until the guard comes.
                slime.held = True
                intruders.append(Intruder(slime, "a slime", "it", self.release_slime(slime)))

        inside = self.plan in ("enter", "eat")

        if inside and not house.knock(quest, "traveler"):
            # Put the bread down and wait for the guard.
            self.set_plan("escorted")
            intruders.append(Intruder(self.traveler, "the traveler", "them", self.release_traveler))

        captain_welcome = house.knock(quest, "captain")

        if self.captain_at in ("inside", "visiting") and not captain_welcome:
            # Stop where they are, on the way in or inside, and wait for the guard.
            self.captain_at = "shownOut"
            intruders.append(Intruder(self.captain, "the Captain", "them", self.captain_goes_home))

        for intruder in intruders:
            yield from self.show_out(intruder)

        yield from self.guard_goes_back()

        # Door rules of the player's own now let knights in: the Captain comes to say hello.
        own_rules = quest.progress["house_rules"] is not None

        if own_rules and captain_welcome and not self.captain_was_welcome and self.captain_at == "guild":
            g.start(self.captain_visits())

        self.captain_was_welcome = captain_welcome

    def release_slime(self, slime):
        def release():
            slime.home = "fields"
            slime.held = False

        return release

    def release_traveler(self):
        # Shown out, they don't come straight back.
        self.set_plan("roam")
        self.next_visit = self.g.now + VISIT_MS

    def show_out(self, intruder):
        """A guard comes in through the door, walks up to the intruder, and leads them out, one step behind."""
        g = self.g
        body = intruder.body

        # Let them finish the step they're on. Anyone already outside needs no guard.
        while body.moving(g.now):
            yield 100

        if not in_house(body.x, body.y) and (body.x, body.y) != DOOR:
            intruder.release()

            return

        guard = self.guard or self.call_guard()

        def beside(p):
            return abs(p[0] - body.x) + abs(p[1] - body.y) == 1

        for step in self.path_for(guard, beside, True):
            yield from self.wait_until_free(step)
            yield from self.walk_body(guard, step)

        if self.near(DOOR):
            g.toast(
                "A guard shows %s out. Your new door rules don't let %s in." % (intruder.name, intruder.pronoun),
                "allow",
            )

        # Out the door, with the intruder following in the guard's footsteps.
        for step in self.path_for(guard, lambda p: p == OUTSIDE, True):
            yield from self.wait_until_free(step)
            behind = (guard.x, guard.y)
            self.step(body, behind)
            yield from self.walk_body(guard, step)

        intruder.release()

    def guard_post(self):
        """Where the house's guard waits: on the grass just inside the gate nearest the house, out of the road."""
        g = self.g

        def distance(guard):
            return abs(guard.gate["x"] - DOORSTEP[0]) + abs(guard.gate["y"] - DOORSTEP[1])

        gate = min(g.guards, key=distance).gate if g.guards else None

        if not gate:
            return OUTSIDE

        def beside(p):
            near_gate = max(abs(p[0] - gate["x"]), abs(p[1] - gate["y"])) == 1
            grass = g.tile(p[0], p[1]) in (TILE["grass"], TILE["flowers"])

            return near_gate and grass and self.can_enter(p)

        path = self.path_for(DOORSTEP, beside)

        return path[-1] if path else OUTSIDE

    def call_guard(self):
        """The first time the house needs a guard, one comes through the nearest gate."""
        post = self.guard_post()
        self.guard = self.g.make_sprite(post[0], post[1], data.GUARD_FRAME)

        return self.guard

    def guard_goes_back(self):
        """Once everyone unwelcome is outside, the guard walks back to wait by the gate."""
        guard = self.guard

        if not guard:
            return

        post = self.guard_post()

        for step in self.path_for(guard, lambda p: p == post):
            yield from self.wait_until_free(step)
            yield from self.walk_body(guard, step)

    def walk_body(self, body, to):
        self.step(body, to)
        yield STEP_MS

    def wait_until_free(self, p):
        """Waits a little while for a tile to clear, then goes ahead regardless, so nobody waits forever."""
        tries = 0

        while tries < 20 and not self.can_enter(p):
            tries += 1
            yield 300

    # The Captain

    def captain_visits(self):
        """The Captain appears on the path outside, comes in, says hello, and goes back to the guild later."""
        g = self.g
        captain = self.captain
        self.captain_at = "visiting"
        yield from self.wait_until_free(OUTSIDE)
        g.teleport(captain, OUTSIDE)

        for step in self.path_for(captain, lambda p: p == CAPTAIN_SPOT, True):
            yield from self.wait_until_free(step)

            # New rules could have turned them away on the way in.
            if self.captain_at != "visiting":
                return

            yield from self.walk_body(captain, step)

        self.captain_at = "inside"

        if in_house(g.player.x, g.player.y) or self.near(DOOR):
            g.toast(
                "The Captain drops by: \"Hello! Your door lets knights in, so I thought I'd say hello.\"", "allow"
            )

        yield CAPTAIN_STAYS_MS

        # Shown out by a guard in the meantime, or still here and ready to go.
        if self.captain_at != "inside" or self.escorting:
            return

        for step in self.path_for(captain, lambda p: p == OUTSIDE, True):
            yield from self.wait_until_free(step)
            yield from self.walk_body(captain, step)

        self.captain_goes_home()

    def captain_goes_home(self):
        self.g.teleport(self.captain, self.captain_home)
        self.captain_at = "guild"
