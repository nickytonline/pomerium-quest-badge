# The quest's progression and everything the badge saves. A port of the browser game's quest statechart
# (app/src/game/quest-machine.ts): each stage is a step in how the player's identity changes.
#
#   anonymous → newcomer → invited → granted → citizen → proven → knighted → knight → armed
#
# `granted` and `knighted` are stale sessions: the Oracle (the identity provider) lists the new group,
# but the session still holds the claims from sign-in until the player signs in again.
#
# The badge has no identity provider, so this module plays it: `oracle_groups()` is what the Oracle
# lists for the player, and `session` is what they signed in with.

import data
import ppl

STAGES = ("anonymous", "newcomer", "invited", "granted", "citizen", "proven", "knighted", "knight", "armed")

GROUPS = data.GROUPS
KNIGHT_QUOTA = data.KNIGHT_QUOTA

#: The player's address at the Oracle.
EMAIL = "you@quest.example"

#: The id of the player's house, which the Oracle's deed claim names.
HOUSE_ID = "house-1"

#: Health counts half hearts.
MAX_HP = 10

#: The access log keeps this many requests.
LOG_SIZE = 30

SAVE_VERSION = 1

#: What each stage does with a sign-in, given the groups the new session carries.
SIGN_IN = {
    "anonymous": lambda groups: "citizen" if GROUPS["citizens"] in groups else "newcomer",
    "newcomer": lambda groups: "citizen" if GROUPS["citizens"] in groups else None,
    "invited": lambda groups: "citizen" if GROUPS["citizens"] in groups else None,
    "granted": lambda groups: "citizen" if GROUPS["citizens"] in groups else None,
    "knighted": lambda groups: "knight" if GROUPS["knights"] in groups else None,
}

#: The other events, and where each one leads from each stage.
EVENTS = {
    "SAGE_SPOKE": {"newcomer": "invited"},
    "CITIZEN_GRANTED": {"invited": "granted"},
    "KNIGHTED": {"proven": "knighted"},
    "STEEL_TAKEN": {"knight": "armed"},
}


def fresh_progress():
    return {
        "books_read": [],
        "scholar": False,
        "fountain_healed": 0,
        "fish_eaten": 0,
        "broken_rocks": [],
        "phish_turned_away": [],
        "lessons": [],
        "letter": 0,
        "house_rules": None,
        "pos": None,
        "dir": "down",
    }


class Quest:
    def __init__(self):
        self.stage = "anonymous"
        self.defeated = 0
        self.session = ppl.identity()
        self.hp = MAX_HP
        self.progress = fresh_progress()
        self.log = []
        self.dirty = False

    # Progression

    def at_least(self, stage):
        return STAGES.index(self.stage) >= STAGES.index(stage)

    def send(self, event):
        target = EVENTS[event].get(self.stage)

        if target:
            self.stage = target
            self.settle()

    def settle(self):
        """A citizen who has already beaten enough slimes is proven straight away."""
        if self.stage == "citizen" and self.defeated >= KNIGHT_QUOTA:
            self.stage = "proven"

        self.dirty = True

    def defeat_monster(self):
        self.defeated += 1
        self.settle()

    # Identity

    def oracle_groups(self):
        """The groups the Oracle lists for the player now, whether or not their session carries them yet."""
        groups = []

        if self.at_least("granted"):
            groups.append(GROUPS["citizens"])

        if self.at_least("knighted"):
            groups.append(GROUPS["knights"])

        if self.progress["scholar"]:
            groups.append(GROUPS["scholars"])

        return groups

    def oracle_deed(self):
        return HOUSE_ID if self.at_least("granted") else None

    def stale(self):
        """What the Oracle has added that the session doesn't carry yet."""
        missing = [group for group in self.oracle_groups() if group not in self.session["groups"]]

        if self.oracle_deed() and not self.session["deed"]:
            missing.append("your deed")

        return missing

    def sign_in(self):
        """The Oracle signs the player in: the new session carries everything he lists for them now."""
        groups = self.oracle_groups()
        self.session = ppl.identity(True, EMAIL, groups, self.oracle_deed())
        move = SIGN_IN.get(self.stage)
        target = move(groups) if move else None

        if target:
            self.stage = target

        self.settle()

    def has_steel(self):
        return self.stage == "armed"

    # Bookkeeping

    def learn(self, lesson):
        """Records a lesson; true the first time."""
        if lesson in self.progress["lessons"]:
            return False

        self.progress["lessons"].append(lesson)
        self.dirty = True

        return True

    def record(self, decision, method, path, who):
        self.log.insert(0, {"decision": decision, "method": method, "path": path, "who": who})
        del self.log[LOG_SIZE:]
        self.dirty = True

    def set_hp(self, hp):
        self.hp = max(0, min(MAX_HP, hp))
        self.dirty = True

    def update(self, **changes):
        self.progress.update(changes)
        self.dirty = True

    # Saving

    def to_save(self):
        return {
            "version": SAVE_VERSION,
            "stage": self.stage,
            "defeated": self.defeated,
            "session": self.session,
            "hp": self.hp,
            "progress": self.progress,
            "log": self.log,
        }

    @classmethod
    def from_save(cls, saved):
        quest = cls()

        if not saved or saved.get("version") != SAVE_VERSION or saved.get("stage") not in STAGES:
            return quest

        quest.stage = saved["stage"]
        quest.defeated = saved.get("defeated", 0)
        session = saved.get("session") or {}
        quest.session = ppl.identity(
            session.get("authenticated", False),
            session.get("email", ""),
            session.get("groups", ()),
            session.get("deed"),
        )
        quest.hp = saved.get("hp", MAX_HP) or MAX_HP
        quest.progress.update(saved.get("progress") or {})
        quest.log = saved.get("log") or []

        return quest
