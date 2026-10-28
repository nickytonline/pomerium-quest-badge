# Plays chapter one and the house on a connected badge, through the game's own input, and prints a
# checkpoint at each step. Run it with: python3 scripts/play.py --fresh --setup "$(cat tests/badge_playthrough.py)"
# The game is `g`, and `now` is the game clock.

import game as gm

clock = [now]


def frames(count, pressed=(), held=()):
    for index in range(count):
        g.update(set(pressed) if index == 0 else set(), set(held), clock[0])
        clock[0] += 33


def press(name, times=1):
    for _ in range(times):
        frames(6, (name,))


def finish_dialogs(limit=60):
    """Presses Select until nothing is open, picking the last choice of any question."""
    for _ in range(limit):
        if g.overlay is None:
            return

        if isinstance(g.overlay, gm.Pages) and g.overlay.asking():
            press("down")

        press("select")


def at(x, y, facing):
    g.player = gm.Sprite(x, y)
    g.dir = facing


def walk(direction, steps):
    for _ in range(steps):
        frames(6, (direction,), (direction,))


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)


g.close(g.overlay)
finish_dialogs()

# Sign in with the Oracle, become a citizen.
at(12, 26, "up")
press("select")
finish_dialogs()
at(4, 21, "up")
press("select")
finish_dialogs()
check("signed in as a newcomer", g.quest.stage == "newcomer")
at(12, 26, "up")
press("select")
finish_dialogs()
at(4, 21, "up")
press("select")
finish_dialogs()
check("a citizen with a deed", g.quest.stage == "citizen" and g.quest.session["deed"] == "house-1")

# Through the Fields Gate: the guard steps aside and the dog walks through.
at(8, 19, "up")
walk("up", 4)
finish_dialogs()
check("through the fields gate", g.player.y < 17)
check("the gate closed behind", g.tile(8, 17) == gm.TILE["gateClosed"])

# The house door opens for its owner; the desk's first letter.
at(8, 12, "left")
walk("left", 2)
finish_dialogs()
check("inside the house", gm.in_house(g.player.x, g.player.y))
at(3, 10, "left")
g.pick_choice = 0
press("select")

for _ in range(10):
    if isinstance(g.overlay, gm.Picker):
        press("select")
    elif g.overlay:
        press("select")

check("first letter solved", g.quest.progress["letter"] == 1)

# Slimes: three for the Captain.
for monster in list(g.monsters)[:3]:
    monster.hp = 1
    at(monster.x - 1, monster.y, "right")
    press("back")

finish_dialogs()
check("three slimes defeated", g.quest.defeated >= 3 and g.quest.stage == "proven")

# The Captain knights the player, and the Oracle arrives to sign them in again.
at(21, 5, "up")
press("select")
finish_dialogs()
check("a knight", g.quest.stage == "knight")
check("the Oracle went home", g.visiting_oracle is None)

# The chest in the armory, then the rocks.
at(33, 5, "up")
press("select")
finish_dialogs()
check("holding the steel sword", g.quest.has_steel())
at(27, 16, "down")
press("back")
check("the rock split", g.tile(27, 17) == gm.TILE["cobble"])

# Through the library gate, every book, the Librarian.
at(33, 19, "down")
walk("down", 3)
finish_dialogs()
check("inside the library", g.player.y > 20)

for shelf in (30, 31, 32):
    at(shelf, 23, "up")
    press("select")
    finish_dialogs()

at(34, 26, "up")
press("select")
finish_dialogs()
check("a scholar in session", "scholars" in g.quest.session["groups"])

# The scriptorium turns everyone away.
at(31, 24, "left")
walk("left", 1)
check("the scriptorium refused", isinstance(g.overlay, gm.Denial))
finish_dialogs()

# The Royal Keep.
at(21, 27, "down")
walk("down", 1)
check("the keep's guard let us by", g.open_gate is not None)
finish_dialogs()
check("the finale was shown", "allOf" in g.quest.progress["lessons"])

g.save(True)
print("lessons", len(g.quest.progress["lessons"]), "log", len(g.quest.log))
