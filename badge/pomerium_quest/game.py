# The kingdom on the badge: movement, guards and gates, slimes, fish, phish and the sword, drawn from the
# browser game's sprite sheets. A port of the browser game's scene.ts. The game takes its input as sets of
# buttons, so a script can play it too (see scripts/play.py).

import json
import random

import data
import house
import story
import ui
from quest import MAX_HP, Quest

TILE = data.TILE
T = data.TILE_PX
MAP_W = data.MAP_WIDTH
MAP_H = data.MAP_HEIGHT
WALKABLE = set(data.WALKABLE)
PLAYER_TERRAIN = set(data.PLAYER_TERRAIN)
HOUSE = data.HOUSE

SAVE_PATH = "/state/pomerium_quest.json"

STEP_MS = 140
WALK_FRAME_MS = 83
SWING_MS = 180
HURT_MS = 900
TOAST_MS = 2800
SAVE_EVERY_MS = 3000
FOUNTAIN_MS = 300

#: A monster's bite takes a full heart (health counts half hearts).
HIT_DAMAGE = 2
BOT_HP = 2

#: Fish swim in each pond, at most FISH_MAX at a time; a new one arrives FISH_RESPAWN_MS after one is eaten.
PONDS = ((2, 25, 4, 27), (2, 5, 5, 7))
FISH_MAX = 2
FISH_RESPAWN_MS = 30000

#: A phish within `reach` steps calls out to the player, at most once every `ms`.
PHISH_REACH = 3
PHISH_CALL_MS = 20000

#: Monsters never leave the fields.
FIELDS = (1, 1, 15, 16)

#: How often a slime on the doorstep may try the player's door.
SLIME_KNOCK_MS = 15000

#: Where a slime Pomerium lets in appears, just inside the door.
SLIME_IN = ((5, 13), (6, 12))

#: Rows of the dog's frame left above the waterline while swimming: head and collar.
SWIM_DEPTH = 11

STEP = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
DIRS = ("up", "down", "left", "right")
DOG_FRAME = {"down": 0, "up": 3, "right": 6, "left": 9}

#: Frames in items.png.
SWORD_WOOD = 0
SWORD_STEEL = 1
BOT_FRAME = 3
FISH_FRAME = 5

BUTTONS = {
    "up": BUTTON_UP,
    "down": BUTTON_DOWN,
    "left": BUTTON_LEFT,
    "right": BUTTON_RIGHT,
    "select": BUTTON_SELECT,
    "back": BUTTON_BACK,
    "menu": BUTTON_MENU,
    "home": BUTTON_HOME,
}


def sheet(name, frames):
    source = image.load("assets/" + name)

    return [source.window(index * T, 0, T, T) for index in range(frames)]


def rotated(source, quarter_turns):
    """A copy of a 16x16 sprite turned clockwise, for the sword's four directions."""
    out = image(T, T)
    out.pen = color.rgb(0, 0, 0, 0)
    out.clear()

    for y in range(T):
        for x in range(T):
            pixel = source.get(x, y)
            nx, ny = x, y

            for _ in range(quarter_turns):
                nx, ny = T - 1 - ny, nx

            out.pen = pixel
            out.put(nx, ny)

    return out


def region_at(x, y):
    inside = HOUSE["inside"]

    if inside["x0"] <= x <= inside["x1"] and inside["y0"] <= y <= inside["y1"]:
        return "Your House"

    if (x, y) == (HOUSE["door"]["x"], HOUSE["door"]["y"]):
        return "Your House"

    if x <= 15:
        return "Hearth Village" if y >= 18 else "Slime Fields"

    return "Library Quarter" if y >= 18 else "Kingdom Town"


def in_house(x, y):
    inside = HOUSE["inside"]

    return inside["x0"] <= x <= inside["x1"] and inside["y0"] <= y <= inside["y1"]


def in_fields(x, y):
    return FIELDS[0] <= x <= FIELDS[2] and FIELDS[1] <= y <= FIELDS[3]


def is_fountain(tile):
    return TILE["fountainTopLeft"] <= tile <= TILE["fountainBottomRight"]


class Sprite:
    """Anything on the map that moves a tile at a time and glides between tiles."""

    def __init__(self, x, y, frame=0):
        self.x = x
        self.y = y
        self.frame = frame
        self.from_x = x
        self.from_y = y
        self.moved_at = -10000
        self.glide_ms = STEP_MS
        self.next_move = 0
        self.hp = BOT_HP
        self.flash_until = 0

    def move(self, x, y, now, glide_ms=STEP_MS):
        self.from_x, self.from_y = self.x, self.y
        self.x, self.y = x, y
        self.moved_at = now
        self.glide_ms = glide_ms

    def moving(self, now):
        return now - self.moved_at < self.glide_ms

    def pixel(self, now):
        """Where to draw, gliding from the last tile to this one."""
        progress = min(1, (now - self.moved_at) / self.glide_ms)

        return (
            (self.from_x + (self.x - self.from_x) * progress) * T,
            (self.from_y + (self.y - self.from_y) * progress) * T,
        )


# What's open over the kingdom


class Pages:
    """Dialog pages, with Select to go on; `choices` turns the last page into a question."""

    def __init__(self, pages, then=None, choices=None):
        self.parts = [part for page in pages for part in ui.screens_of(page)]
        self.index = 0
        self.then = then
        self.choices = choices
        self.selected = 0
        self.full = self.parts[0]["kind"] == "code"

    def asking(self):
        return self.choices and self.index >= len(self.parts)

    def handle(self, game, pressed):
        if self.asking():
            if "up" in pressed or "down" in pressed:
                self.selected = (self.selected + 1) % len(self.choices)

            if "select" in pressed:
                game.close(self, self.choices[self.selected][1])

            return

        if "select" in pressed or ("back" in pressed and not self.choices):
            self.index += 1

            if self.index >= len(self.parts):
                if not self.choices:
                    game.close(self, self.then)

                return

        self.full = self.parts[self.index]["kind"] == "code"

    def draw(self, game, now):
        if self.asking():
            ui.choices(self.choices, self.selected, now)

            return

        part = self.parts[self.index]
        self.full = part["kind"] == "code"
        ui.dialog(part, now, self.index == len(self.parts) - 1 and not self.choices)


class Denial:
    def __init__(self, view, then=None):
        self.view = view
        self.parts = ui.deny_parts(view)
        self.index = 0
        self.then = then
        self.full = True

    def handle(self, game, pressed):
        if "back" in pressed:
            game.close(self, self.then)
        elif "select" in pressed:
            self.index += 1

            if self.index >= len(self.parts):
                game.close(self, self.then)

    def draw(self, game, now):
        ui.deny(self.view, self.parts[self.index], now, self.index == len(self.parts) - 1)


class Picker:
    """The desk: compare door rules with Left and Right, choose one with Select."""

    def __init__(self, title, options, chosen):
        self.title = title
        self.options = options
        self.chosen = chosen
        self.selected = 0
        self.full = True

    def handle(self, game, pressed):
        if "left" in pressed or "up" in pressed:
            self.selected = (self.selected - 1) % len(self.options)

        if "right" in pressed or "down" in pressed:
            self.selected = (self.selected + 1) % len(self.options)

        if "select" in pressed:
            index = self.selected
            game.close(self, lambda: self.chosen(index))
        elif "back" in pressed:
            game.close(self)

    def draw(self, game, now):
        ui.pick(self.title, self.options, self.selected, now)


JOURNAL_TABS = ("Quest", "Papers", "Lessons", "Log", "Start over")


class Journal:
    def __init__(self):
        self.tab = 0
        self.row = 0
        self.qr = None
        self.confirm = False
        self.full = True

    def handle(self, game, pressed):
        if self.qr:
            if pressed & {"back", "select", "menu"}:
                self.qr = None

            return

        if "menu" in pressed or "back" in pressed:
            game.close(self)

            return

        if "left" in pressed or "right" in pressed:
            step = 1 if "right" in pressed else -1
            self.tab = (self.tab + step) % len(JOURNAL_TABS)
            self.row = 0
            self.confirm = False

        tab = JOURNAL_TABS[self.tab]
        lessons = game.quest.progress["lessons"]

        if tab == "Lessons" and lessons:
            if "up" in pressed:
                self.row = (self.row - 1) % len(lessons)

            if "down" in pressed:
                self.row = (self.row + 1) % len(lessons)

            if "select" in pressed:
                self.qr = data.LESSONS[lessons[self.row]]

        if tab == "Start over" and "select" in pressed:
            if self.confirm:
                game.start_over()
            else:
                self.confirm = True

    def draw(self, game, now):
        quest = game.quest

        if self.qr:
            ui.panel("Docs: " + ui.plain(self.qr["title"]))
            draw_qr(self.qr["link"]["href"])
            ui.centred(self.qr["link"]["label"], ui.HEIGHT - 36, ui.MUTED)
            ui.centred("Scan to read the docs. Back to close.", ui.HEIGHT - 22, ui.MUTED)

            return

        ui.panel("Journal")
        ui.tabs(JOURNAL_TABS, self.tab)
        tab = JOURNAL_TABS[self.tab]
        y = 52

        if tab == "Quest":
            y = ui.paragraph(goal(quest), y)
            y += 8
            ui.paragraph(
                "Slimes defeated: %d    Books read: %d of %d"
                % (quest.defeated, len(quest.progress["books_read"]), len(data.BOOKS)),
                y,
                ui.MUTED,
            )
        elif tab == "Papers":
            if not quest.session["authenticated"]:
                ui.paragraph("You have no papers yet: no session. The Oracle in Hearth Village can sign you in.", y)
            else:
                y = ui.paragraph("Your session's claims, as every guard reads them:", y, ui.MUTED)
                y = ui.code(story.claims_code(quest.session), ui.PAD + 4, y + 2)
                stale = quest.stale()

                if stale:
                    ui.paragraph("The Oracle also lists " + ", ".join(stale) + ". Sign in again to carry it.", y + 4, ui.SUN)
        elif tab == "Lessons":
            lessons = quest.progress["lessons"]

            if not lessons:
                ui.paragraph("Lessons you learn on your quest gather here.", y)

            first = max(0, self.row - 10)

            for index in range(first, min(len(lessons), first + 11)):
                pen = ui.LIME if index == self.row else ui.TEXT
                ui.text(ui.plain(data.LESSONS[lessons[index]]["title"]), ui.PAD + 12, y, pen)

                if index == self.row:
                    ui.mark(True, ui.PAD + 1, y + 2)

                y += ui.LINE + 2

            ui.text("Up/Down: choose   Select: docs as a QR code", ui.PAD + 4, ui.HEIGHT - 20, ui.MUTED)
        elif tab == "Log":
            if not quest.log:
                ui.paragraph("Every request a guard checks shows up here.", y)

            for entry in quest.log[:13]:
                pen = ui.LIME if entry["decision"] == "ALLOW" else ui.RED
                ui.text(entry["decision"], ui.PAD + 4, y, pen)
                ui.text(entry["method"] + " " + entry["path"], ui.PAD + 58, y, ui.CODE)
                y += ui.LINE + 1
        else:
            y = ui.paragraph("Forget your progress and start the quest again from the beginning.", y)

            if self.confirm:
                ui.paragraph("Are you sure? Press Select again to start over.", y + 8, ui.RED)
            else:
                ui.paragraph("Press Select to start over.", y + 8, ui.SUN)

        if tab not in ("Lessons",):
            ui.text("Left/Right: tabs   Back or Menu: close", ui.PAD + 4, ui.HEIGHT - 20, ui.MUTED)


class Title:
    def __init__(self, saved):
        self.saved = saved
        self.full = True

    def handle(self, game, pressed):
        if "select" in pressed:
            game.close(self, game.begin)

    def draw(self, game, now):
        ui.panel("Pomerium Quest")
        dog = game.dog[DOG_FRAME["down"] + (now // 300) % 3]
        screen.blit(dog, rect(0, 0, T, T), rect(ui.WIDTH // 2 - 32, 50, 64, 64))
        ui.centred("A Pomeranian, a kingdom of gates,", 130, ui.TEXT)
        ui.centred("and a guard at every one of them.", 144, ui.TEXT)
        ui.centred("Press Select to " + ("continue" if self.saved else "start"), 180, ui.LIME)
        ui.centred("Home: back to the badge menu", 206, ui.MUTED)


def draw_qr(url):
    """The docs link as a QR code, on a white square so phones can read it."""
    code = screen.qr(url)
    scale = min(4, 150 // code.width)
    size = code.width * scale
    x = (ui.WIDTH - size) // 2
    y = 34
    screen.pen = color.rgb(255, 255, 255)
    screen.rectangle(x - 8, y - 8, size + 16, size + 16)
    screen.blit(code, rect(0, 0, code.width, code.height), rect(x, y, size, size))


def goal(quest):
    """What to do next, for the journal."""
    stage = quest.stage
    letter_id, letter = house.current_letter(quest)

    goals = {
        "anonymous": "Talk to the sage in the house beside you, then visit the Oracle in his temple to the west.",
        "newcomer": "Talk to the sage again: they have news for you.",
        "invited": "Visit the Oracle: he'll make you a citizen and give you the deed to your house.",
        "granted": "Sign in again at the Oracle's temple, so your session carries your new claims.",
        "citizen": "Defeat %d bot slimes in the Slime Fields (%d so far), then see the Captain in the Knights' "
        "Guild, north of the town square." % (story.KNIGHT_QUOTA, quest.defeated),
        "proven": "Report to the Captain in the Knights' Guild, north of the town square.",
        "knighted": "Sign in again with the Oracle, so your session says knights.",
        "knight": "Take the steel sword from the chest in the armory, east of the square.",
    }
    text = goals.get(stage)

    if text is None:
        books = len(quest.progress["books_read"])

        if quest.stale():
            text = "Sign in again with the Oracle, so your session carries your new claims."
        elif not quest.progress["scholar"]:
            text = (
                "Break the cracked rocks south of the square with your steel sword, then read every book in the "
                "Royal Library (%d of %d) and talk to the Librarian." % (books, len(data.BOOKS))
            )
        else:
            text = "Walk the road south, just west of the library, to the Royal Keep."

    if letter:
        text += " A letter waits on the desk in your house: " + letter["title"]

    return text


class Game:
    def __init__(self):
        self.dog = sheet("dog.png", 12)
        self.items = sheet("items.png", 7)
        self.npc_frames = sheet("npcs.png", 9)
        self.tile_frames = sheet("tiles.png", 42)
        self.swords = {
            frame: {direction: rotated(self.items[frame], turns) for direction, turns in (("up", 0), ("right", 1), ("down", 2), ("left", 3))}
            for frame in (SWORD_WOOD, SWORD_STEEL)
        }
        self.board = image(MAP_W * T, MAP_H * T)
        self.board.antialias = image.OFF
        self.overlay = None
        self.queue = []
        self.toasts = []
        self.toast_until = 0
        self.saved_at = 0
        self.now = 0
        self.quest = Quest.from_save(self.load())
        saved = self.quest.progress["pos"] is not None
        self.reset_world()
        self.show(Title(saved))

    # Saving

    def load(self):
        try:
            with open(SAVE_PATH) as file:
                return json.load(file)
        except (OSError, ValueError):
            return None

    def save(self, force=False):
        if not self.quest.dirty and not force:
            return

        self.quest.update(pos=[self.player.x, self.player.y], dir=self.dir)
        self.quest.dirty = False

        try:
            with open(SAVE_PATH, "w") as file:
                json.dump(self.quest.to_save(), file)
        except OSError:
            pass

    def start_over(self):
        try:
            import os

            os.remove(SAVE_PATH)
        except OSError:
            pass

        self.quest = Quest()
        self.overlay = None
        self.queue = []
        self.toasts = []
        self.reset_world()
        self.show(Title(False))

    # The world

    def reset_world(self):
        quest = self.quest
        self.tiles = [bytearray(row) for row in data.MAP]

        for key in quest.progress["broken_rocks"]:
            x, y = key
            self.tiles[y][x] = TILE["cobble"]

        if quest.has_steel():
            self.tiles[data.CHEST["y"]][data.CHEST["x"]] = TILE["chestOpen"]

        self.sync_house_tiles()
        pos = quest.progress["pos"] or [data.SPAWN["x"], data.SPAWN["y"]]
        self.player = Sprite(pos[0], pos[1])
        self.dir = quest.progress["dir"] or "down"
        self.swing_at = -10000
        self.hurt_at = -10000
        self.npcs = [Sprite(npc["x"], npc["y"], data.NPC_FRAME[npc["npcId"]]) for npc in data.NPCS]

        for sprite, npc in zip(self.npcs, data.NPCS):
            sprite.npc_id = npc["npcId"]

        self.visiting_oracle = None
        self.guards = []

        for gate in data.GATES:
            post = self.post_of(gate)
            guard = Sprite(post[0], post[1], data.GUARD_FRAME)
            guard.gate = gate
            guard.post = post
            self.guards.append(guard)

        self.open_gate = None
        self.monsters = []

        for bot in data.BOTS:
            monster = Sprite(bot["x"], bot["y"], BOT_FRAME)
            monster.home = "fields"
            self.monsters.append(monster)

        self.fish = []
        turned = quest.progress["phish_turned_away"]
        self.phish = []

        for index, spot in enumerate(data.PHISH):
            if index not in turned:
                phish = Sprite(spot["x"], spot["y"], data.PHISH_FRAME)
                phish.index = index
                phish.called_at = -PHISH_CALL_MS
                self.phish.append(phish)

        self.fish_due = []

        for pond in PONDS:
            for _ in range(FISH_MAX):
                self.spawn_fish(pond)

        self.slime_knocked_at = -SLIME_KNOCK_MS
        self.fountain_frame = 0
        self.draw_board()

    def sync_house_tiles(self):
        """The door opens once the Oracle grants the deed; a letter waiting shows on the desk."""
        door = HOUSE["door"]
        desk = HOUSE["desk"]
        owned = house.stage(self.quest) != "unowned"
        self.set_tile(door["x"], door["y"], TILE["door"] if owned else TILE["doorLocked"], False)
        letter = house.current_letter(self.quest)[1]
        self.set_tile(desk["x"], desk["y"], TILE["deskLetter"] if letter else TILE["desk"], False)

    def tile(self, x, y):
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            return self.tiles[y][x]

        return TILE["tree"]

    def set_tile(self, x, y, tile, draw=True):
        self.tiles[y][x] = tile

        if draw:
            self.draw_tile(x, y)

    def draw_tile(self, x, y):
        tile = self.tiles[y][x]

        if is_fountain(tile):
            tile += self.fountain_frame * 4

        self.board.blit(self.tile_frames[tile], vec2(x * T, y * T))

    def draw_board(self):
        for y in range(MAP_H):
            for x in range(MAP_W):
                self.draw_tile(x, y)

    def animate_fountain(self):
        frame = (self.now // FOUNTAIN_MS) % data.FOUNTAIN_FRAMES

        if frame == self.fountain_frame:
            return

        self.fountain_frame = frame
        fountain = data.FOUNTAIN

        for dy in (0, 1):
            for dx in (0, 1):
                self.draw_tile(fountain["x"] + dx, fountain["y"] + dy)

    def post_of(self, gate):
        """A guard's post is the tile in front of their gate, on the outside, where the gate's sign stands."""
        sign = next((s for s in data.SIGNS if s["signId"] == gate["signId"]), gate)
        road_runs_across = self.tile(gate["x"] - 1, gate["y"]) in PLAYER_TERRAIN

        if road_runs_across:
            return (gate["x"] - 1 if sign["x"] < gate["x"] else gate["x"] + 1, gate["y"])

        return (gate["x"], gate["y"] + 1 if sign["y"] > gate["y"] else gate["y"] - 1)

    def aside_of(self, guard):
        """Where a guard steps to let the player by: to one side of their post, away from the sign."""
        gate = guard.gate
        post = guard.post
        across = (post[1] - gate["y"], post[0] - gate["x"])
        sign = next((s for s in data.SIGNS if s["signId"] == gate["signId"]), None)
        sign = (sign["x"], sign["y"]) if sign else post
        away = -1 if (sign[0] - post[0]) * across[0] + (sign[1] - post[1]) * across[1] > 0 else 1
        choices = (
            (post[0] + across[0] * away, post[1] + across[1] * away),
            (post[0] - across[0] * away, post[1] - across[1] * away),
            (post[0] * 2 - gate["x"], post[1] * 2 - gate["y"]),
        )

        for x, y in choices:
            if self.tile(x, y) in WALKABLE and not self.occupied(x, y) and (x, y) != (self.player.x, self.player.y):
                return (x, y)

        return post

    def occupied(self, x, y):
        for group in (self.npcs, self.monsters, self.fish, self.phish):
            for sprite in group:
                if sprite.x == x and sprite.y == y:
                    return True

        for guard in self.guards:
            if (guard.x, guard.y) == (x, y):
                return True

        oracle = self.visiting_oracle

        return bool(oracle and (oracle.x, oracle.y) == (x, y))

    def find(self, group, x, y):
        for sprite in group:
            if sprite.x == x and sprite.y == y:
                return sprite

        return None

    # What story.py and house.py call

    def show(self, overlay):
        if self.overlay is None:
            self.overlay = overlay
        else:
            self.queue.append(overlay)

    def close(self, overlay, then=None):
        if self.overlay is overlay:
            self.overlay = None

        if then:
            then()

        if self.overlay is None and self.queue:
            self.overlay = self.queue.pop(0)

        self.sync_house_tiles_if_changed()

    def say(self, pages, then=None):
        self.show(Pages(pages, then))

    def ask(self, pages, choices):
        self.show(Pages(pages, None, choices))

    def deny(self, view, then=None):
        self.show(Denial(view, then))

    def pick(self, title, options, chosen):
        self.show(Picker(title, options, chosen))

    def toast(self, text, tone="info"):
        if len(self.toasts) < 4:
            self.toasts.append((text, tone))

    def oracle_beside(self, shown):
        if not shown:
            self.visiting_oracle = None

            return

        for direction in DIRS:
            dx, dy = STEP[direction]
            x, y = self.player.x + dx, self.player.y + dy

            if self.tile(x, y) in PLAYER_TERRAIN and not self.occupied(x, y):
                self.visiting_oracle = Sprite(x, y, data.NPC_FRAME["oracle"])

                return

    def finale(self):
        self.say(story.FINALE)

    def phished(self):
        self.say(story.PHISHED, self.start_over)

    def begin(self):
        if self.quest.progress["pos"] is None:
            self.quest.update(pos=[self.player.x, self.player.y])
            self.say(story.INTRO)

    def sync_house_tiles_if_changed(self):
        door = HOUSE["door"]
        desk = HOUSE["desk"]
        before = (self.tiles[door["y"]][door["x"]], self.tiles[desk["y"]][desk["x"]])
        self.sync_house_tiles()
        after = (self.tiles[door["y"]][door["x"]], self.tiles[desk["y"]][desk["x"]])

        if before != after:
            self.draw_tile(door["x"], door["y"])
            self.draw_tile(desk["x"], desk["y"])

    # Playing

    def front(self):
        dx, dy = STEP[self.dir]

        return self.player.x + dx, self.player.y + dy

    def update(self, pressed, held, now):
        self.now = now
        self.animate_fountain()

        if self.overlay:
            if pressed:
                self.overlay.handle(self, pressed)
        else:
            self.play(pressed, held, now)

        self.update_monsters(now)
        self.update_fish(now)
        self.call_out_phish(now)

        if now - self.saved_at > SAVE_EVERY_MS:
            self.saved_at = now
            self.save()

    def play(self, pressed, held, now):
        if "menu" in pressed:
            self.show(Journal())

            return

        if self.player.moving(now):
            return

        if "select" in pressed:
            self.interact()

            return

        if "back" in pressed:
            self.swing()

            return

        for direction in DIRS:
            if direction in held or direction in pressed:
                self.try_move(direction)

                return

    def try_move(self, direction):
        self.dir = direction
        x, y = self.front()

        if self.find(self.npcs, x, y) or self.find(self.phish, x, y):
            return

        oracle = self.visiting_oracle

        if oracle and (oracle.x, oracle.y) == (x, y):
            return

        guard = next((g for g in self.guards if (g.x, g.y) == (x, y)), None)

        if guard:
            if self.open_gate is not guard:
                self.ask_guard(guard, x, y, guard.gate["zoneId"])

            return

        fish = self.find(self.fish, x, y)

        if fish:
            self.catch_fish(fish)

            return

        if self.find(self.monsters, x, y):
            self.hurt(OPPOSITE[direction])

            return

        tile = self.tile(x, y)

        if tile == TILE["gateClosed"]:
            # From inside, the gate stands between the player and the guard outside. Walking out puts the
            # player back in the zone beyond, so the guard checks they still meet its rule.
            guard = next((g for g in self.guards if (g.gate["x"], g.gate["y"]) == (x, y)), None)

            if guard and guard.gate.get("exitZoneId"):
                self.ask_guard(guard, x, y, guard.gate["exitZoneId"], True)
            elif guard:
                self.let_through(guard)
                self.walk(x, y)

            return

        if tile == TILE["rock"]:
            self.hint("A cracked rock blocks the way. A stronger sword might break it.")

            return

        if tile == TILE["doorLocked"]:
            self.hint("Locked. The sage in Hearth Village knows who holds the deed to this house.")

            return

        door = HOUSE["door"]

        # From outside, the house's own rules decide whether its door opens for the player.
        if (x, y) == (door["x"], door["y"]) and not in_house(self.player.x, self.player.y):
            if not house.knock(self.quest, "you"):
                house.door_refuses_you(self)

                return

        if tile in PLAYER_TERRAIN or tile == TILE["gateOpen"]:
            self.walk(x, y)

    def hint(self, text):
        if not self.toasts:
            self.toast(text)

    def walk(self, x, y):
        self.player.move(x, y, self.now)
        self.arrive()

    def arrive(self):
        player = self.player
        passing = self.open_gate

        if passing:
            gate = (passing.gate["x"], passing.gate["y"])

            if (player.x, player.y) not in (gate, passing.post):
                self.close_gate()

        came_in = in_house(player.x, player.y) and not in_house(player.from_x, player.from_y)

        if came_in:
            self.came_home()

        self.quest.progress["pos"] = [player.x, player.y]
        self.quest.progress["dir"] = self.dir

    def came_home(self):
        if self.quest.progress["house_rules"] is None:
            story.learn(self, "publicRoute")

        letter = house.current_letter(self.quest)[1]

        if letter:
            self.toast("There's a letter on your desk.")

    def ask_guard(self, guard, x, y, zone_id, leaving=False):
        outcome = story.enter_gate(self, zone_id, leaving)

        if outcome == "allow":
            self.let_through(guard)
            self.walk(x, y)
        elif leaving and outcome == "signin":
            self.respawn("Something went wrong and your session was lost, so you start again in Hearth Village.")

    def let_through(self, guard):
        gate = guard.gate
        self.set_tile(gate["x"], gate["y"], TILE["gateOpen"])
        self.open_gate = guard
        aside = self.aside_of(guard)
        guard.move(aside[0], aside[1], self.now)

    def close_gate(self):
        guard = self.open_gate
        self.open_gate = None
        gate = guard.gate
        self.set_tile(gate["x"], gate["y"], TILE["gateClosed"])
        guard.move(guard.post[0], guard.post[1], self.now)

    def interact(self):
        x, y = self.front()
        npc = self.find(self.npcs, x, y)

        if npc:
            story.talk(self, npc.npc_id)

            return

        oracle = self.visiting_oracle

        if oracle and (oracle.x, oracle.y) == (x, y):
            story.talk(self, "oracle")

            return

        phish = self.find(self.phish, x, y)

        if phish:
            story.meet_phish(self, lambda: self.turn_away(phish))

            return

        fish = self.find(self.fish, x, y)

        if fish:
            self.catch_fish(fish)

            return

        if (x, y) == (HOUSE["sign"]["x"], HOUSE["sign"]["y"]):
            house.read_sign(self)

            return

        sign = next((s for s in data.SIGNS if (s["x"], s["y"]) == (x, y)), None)

        if sign:
            gate = next(g for g in data.GATES if g["signId"] == sign["signId"])
            story.read_sign(self, gate["zoneId"])

            return

        guard = next(
            (g for g in self.guards if (g.x, g.y) == (x, y) or (g.gate["x"], g.gate["y"]) == (x, y)),
            None,
        )

        if guard:
            story.read_sign(self, guard.gate["zoneId"])

            return

        tile = self.tile(x, y)

        if tile == TILE["chest"] and story.open_chest(self):
            self.set_tile(x, y, TILE["chestOpen"])
        elif tile == TILE["shelf"]:
            story.read_book(self, x)
        elif is_fountain(tile):
            story.drink_from_fountain(self)
        elif tile == TILE["anvil"]:
            story.read_anvil(self)
        elif tile == TILE["workbench"]:
            story.read_workbench(self)
        elif tile in (TILE["desk"], TILE["deskLetter"]):
            house.use_desk(self)
        elif tile == TILE["tableBread"]:
            house.read_table(self)
        elif tile == TILE["doorLocked"]:
            self.hint("Locked. The sage in Hearth Village knows who holds the deed to this house.")

    def swing(self):
        self.swing_at = self.now
        x, y = self.front()
        monster = self.find(self.monsters, x, y)

        if monster:
            self.hit_monster(monster, 2 if self.quest.has_steel() else 1)

            return

        if self.find(self.phish, x, y):
            self.toast("The robed figure steps back from your swing, smiling. You can't fight a phish, only refuse it.")

            return

        if self.tile(x, y) != TILE["rock"]:
            return

        if not self.quest.has_steel():
            self.hint("Clang. The wooden sword bounces off the cracked rock.")

            return

        self.set_tile(x, y, TILE["cobble"])
        self.quest.update(broken_rocks=self.quest.progress["broken_rocks"] + [[x, y]])
        self.toast("The steel sword splits the rock.")

    def hit_monster(self, monster, damage):
        monster.hp -= damage
        monster.flash_until = self.now + 120

        if monster.hp > 0:
            dx, dy = STEP[self.dir]
            back = (monster.x + dx, monster.y + dy)

            if self.monster_can_enter(monster, back[0], back[1]):
                monster.move(back[0], back[1], self.now, 220)

            return

        self.monsters.remove(monster)

        # An open house would be an endless supply of slimes, so the ones inside don't count for the Captain.
        if monster.home == "house":
            self.toast(
                "Slime defeated. Your door rules keep the rest out."
                if self.quest.progress["house_rules"] is not None
                else "Slime defeated. But your door is public, so the next slime can walk right in."
            )

            return

        self.quest.defeat_monster()
        count = min(self.quest.defeated, story.KNIGHT_QUOTA)
        self.toast("Bot slime defeated (%d of %d for the Captain)" % (count, story.KNIGHT_QUOTA))

    def monster_can_enter(self, monster, x, y):
        area = in_house(x, y) if monster.home == "house" else in_fields(x, y) and not in_house(x, y)

        return (
            area
            and self.tile(x, y) in WALKABLE
            and not self.occupied(x, y)
            and (x, y) != (self.player.x, self.player.y)
        )

    def update_monsters(self, now):
        if self.overlay:
            return

        for monster in self.monsters:
            if monster.moving(now) or now < monster.next_move:
                continue

            monster.next_move = now + 600 + random.randint(0, 700)
            dx = self.player.x - monster.x
            dy = self.player.y - monster.y
            chase = abs(dx) + abs(dy) <= 5 and random.random() < 0.6

            if chase:
                direction = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
            else:
                direction = random.choice(DIRS)

            step = STEP[direction]
            x, y = monster.x + step[0], monster.y + step[1]

            if (x, y) == (self.player.x, self.player.y) and not self.player.moving(now):
                self.hurt(direction)

                continue

            if self.monster_can_enter(monster, x, y):
                monster.move(x, y, now, 220)

            doorstep = HOUSE["doorstep"]

            if monster.home == "fields" and (monster.x, monster.y) == (doorstep["x"], doorstep["y"]):
                self.slime_at_door(monster)

    def slime_at_door(self, monster):
        """A field slime on the doorstep tries the door: a request with no session."""
        if house.stage(self.quest) == "unowned" or self.now - self.slime_knocked_at < SLIME_KNOCK_MS:
            return

        if any(candidate.home == "house" for candidate in self.monsters):
            return

        self.slime_knocked_at = self.now
        door = HOUSE["door"]
        near = abs(self.player.x - door["x"]) + abs(self.player.y - door["y"]) <= 6

        if house.knock(self.quest, "slime"):
            for x, y in SLIME_IN:
                if not self.occupied(x, y) and (x, y) != (self.player.x, self.player.y):
                    monster.move(x, y, self.now, 1)
                    monster.home = "house"
                    break

            if near or in_house(self.player.x, self.player.y):
                self.toast("A slime squeezes in through your public door.", "deny")

            return

        if near:
            self.toast("A slime bounces off your door. With no session, it matches none of your rules.", "allow")

    def spawn_fish(self, pond):
        free = [
            (x, y)
            for y in range(pond[1], pond[3] + 1)
            for x in range(pond[0], pond[2] + 1)
            if self.tile(x, y) == TILE["water"] and not self.occupied(x, y) and (x, y) != (self.player.x, self.player.y)
        ]

        if not free:
            return

        x, y = random.choice(free)
        fish = Sprite(x, y, FISH_FRAME)
        fish.pond = pond
        self.fish.append(fish)

    def catch_fish(self, fish):
        if not story.eat_fish(self):
            return

        self.fish.remove(fish)
        self.fish_due.append((self.now + FISH_RESPAWN_MS, fish.pond))

    def update_fish(self, now):
        for due in list(self.fish_due):
            if now >= due[0]:
                self.fish_due.remove(due)
                self.spawn_fish(due[1])

        if self.overlay:
            return

        for fish in self.fish:
            if fish.moving(now) or now < fish.next_move:
                continue

            fish.next_move = now + 800 + random.randint(0, 1200)
            step = STEP[random.choice(DIRS)]
            x, y = fish.x + step[0], fish.y + step[1]
            pond = fish.pond
            inside = pond[0] <= x <= pond[2] and pond[1] <= y <= pond[3]

            if inside and self.tile(x, y) == TILE["water"] and not self.occupied(x, y):
                fish.move(x, y, now, 400)

    def turn_away(self, phish):
        """A phish the player refused gives up and doesn't come back."""
        self.phish.remove(phish)
        self.quest.update(phish_turned_away=self.quest.progress["phish_turned_away"] + [phish.index])

    def call_out_phish(self, now):
        if self.overlay:
            return

        for phish in self.phish:
            near = abs(phish.x - self.player.x) + abs(phish.y - self.player.y) <= PHISH_REACH

            if near and now - phish.called_at >= PHISH_CALL_MS:
                phish.called_at = now
                self.toast('A robed figure waves you over: "Psst! Your session is about to expire!"')

    def hurt(self, direction):
        """Takes a hit coming from `direction` (the way the attacker was moving)."""
        if self.now - self.hurt_at < HURT_MS:
            return

        self.hurt_at = self.now
        hp = self.quest.hp - HIT_DAMAGE

        if hp <= 0:
            self.respawn()

            return

        self.quest.set_hp(hp)
        step = STEP[direction]
        x, y = self.player.x + step[0], self.player.y + step[1]

        if not self.player.moving(self.now) and self.tile(x, y) in PLAYER_TERRAIN and not self.occupied(x, y):
            self.walk(x, y)

    def respawn(self, message="You wake up back in Hearth Village. Your identity and gear are still yours."):
        if self.open_gate:
            self.close_gate()

        self.player = Sprite(data.SPAWN["x"], data.SPAWN["y"])
        self.quest.set_hp(MAX_HP)
        self.toast(message)

    # Drawing

    def camera(self):
        px, py = self.player.pixel(self.now)
        cx = max(0, min(MAP_W * T - ui.WIDTH, int(px) + T // 2 - ui.WIDTH // 2))
        cy = max(0, min(MAP_H * T - ui.HEIGHT, int(py) + T // 2 - ui.HEIGHT // 2))

        return cx, cy

    def blit(self, frame, sprite, cx, cy, crop=None):
        px, py = sprite.pixel(self.now)
        x, y = int(px) - cx, int(py) - cy

        if x <= -T or y <= -T or x >= ui.WIDTH or y >= ui.HEIGHT:
            return

        screen.blit(frame.window(0, 0, T, crop) if crop else frame, vec2(x, y))

    def draw(self):
        now = self.now
        overlay = self.overlay

        if overlay and overlay.full:
            screen.pen = ui.NIGHT_DEEP
            screen.clear()
            overlay.draw(self, now)

            return

        cx, cy = self.camera()
        screen.blit(self.board.window(cx, cy, ui.WIDTH, ui.HEIGHT), vec2(0, 0))
        wobble = (now // 400) % 2

        for npc in self.npcs:
            self.blit(self.npc_frames[npc.frame], npc, cx, cy)

        for guard in self.guards:
            self.blit(self.npc_frames[guard.frame], guard, cx, cy)

        for phish in self.phish:
            self.blit(self.npc_frames[phish.frame], phish, cx, cy)

        if self.visiting_oracle:
            self.blit(self.npc_frames[self.visiting_oracle.frame], self.visiting_oracle, cx, cy)

        for fish in self.fish:
            self.blit(self.items[FISH_FRAME + wobble], fish, cx, cy)

        for monster in self.monsters:
            if monster.flash_until <= now or (now // 40) % 2:
                self.blit(self.items[BOT_FRAME + wobble], monster, cx, cy)

        self.draw_player(cx, cy)
        ui.hud(self.quest.hp, MAX_HP, region_at(self.player.x, self.player.y))
        self.draw_toast(now)

        if overlay:
            overlay.draw(self, now)

    def draw_player(self, cx, cy):
        now = self.now
        player = self.player
        base = DOG_FRAME[self.dir]
        frame = base

        if player.moving(now):
            frame = base + (1, 0, 2, 0)[(now // WALK_FRAME_MS) % 4]

        hurt = now - self.hurt_at < HURT_MS

        if hurt and (now // 90) % 2:
            return

        swimming = self.tile(player.x, player.y) == TILE["water"]
        self.blit(self.dog[frame], player, cx, cy, SWIM_DEPTH if swimming else None)

        if now - self.swing_at < SWING_MS:
            dx, dy = STEP[self.dir]
            px, py = player.pixel(now)
            sword = self.swords[SWORD_STEEL if self.quest.has_steel() else SWORD_WOOD][self.dir]
            screen.blit(sword, vec2(int(px) - cx + dx * 11, int(py) - cy + dy * 11))

    def draw_toast(self, now):
        if not self.toasts:
            return

        if self.toast_until == 0:
            self.toast_until = now + TOAST_MS

        message, tone = self.toasts[0]
        ui.toast(message, tone)

        if now >= self.toast_until:
            self.toasts.pop(0)
            self.toast_until = 0
