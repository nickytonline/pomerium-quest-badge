# The player's house: a route whose policy the player chooses. A port of the browser game's house-story.ts.
# In the browser the player writes door rules in an editor; on the badge they pick from three at the desk,
# and the letter's visitors try the door against the badge's policy evaluator.

import data
import ppl
from quest import HOUSE_ID
from story import learn, link, page

VISITORS = data.VISITORS
LETTERS = data.LETTERS
LETTER_ORDER = data.LETTER_ORDER

#: The house's path under Pomerium's house routes.
HOUSE_PATH = data.HOUSE_PREFIX + "/" + HOUSE_ID + "/"

ANONYMOUS = ppl.identity()

BAKER_EMAIL = VISITORS["baker"]["email"]
TRAVELER_EMAIL = VISITORS["traveler"]["email"]


def rule(action, match, *criteria):
    return {"action": action, "match": match, "criteria": list(criteria)}


def email(address):
    return {"kind": "email", "is": address}


def group(name):
    return {"kind": "claim", "claim": "groups", "value": name}


def method(name):
    return {"kind": "http_method", "is": name}


SIGNED_IN = {"kind": "authenticated_user"}
ACCEPT = {"kind": "accept"}

#: The rule every house starts with: whoever carries its deed always gets in.
DEED_RULE = rule("allow", "or", {"kind": "claim", "claim": "deed", "value": HOUSE_ID})

#: For each letter, three door policies to choose from. Exactly one does what the letter asks.
OPTIONS = {
    "slimes": (
        ("Let in the traveler", [rule("allow", "or", email(TRAVELER_EMAIL))]),
        ("Let in everyone", [rule("allow", "or", ACCEPT)]),
        ("Let in citizens", [rule("allow", "or", group("citizens"))]),
    ),
    "bread": (
        ("Keep the traveler's rule", [rule("allow", "or", email(TRAVELER_EMAIL))]),
        ("No rules but the deed", []),
        ("Let in anyone signed in", [rule("allow", "or", SIGNED_IN)]),
    ),
    "guild": (
        ("Let in anyone signed in", [rule("allow", "or", SIGNED_IN)]),
        ("Let in the knights", [rule("allow", "or", group("knights"))]),
        ("Let in citizens", [rule("allow", "or", group("citizens"))]),
    ),
    "baker": (
        ("Let in citizens", [rule("allow", "or", group("citizens"))]),
        ("Let in all but the baker", [rule("allow", "not", email(BAKER_EMAIL))]),
        (
            "Citizens, but deny the baker",
            [rule("allow", "or", group("citizens")), rule("deny", "or", email(BAKER_EMAIL))],
        ),
    ),
    "window": (
        ("Knights may look (GET)", [rule("allow", "and", group("knights"), method("GET"))]),
        ("Let in the knights", [rule("allow", "or", group("knights"))]),
        ("Knights may knock (POST)", [rule("allow", "and", group("knights"), method("POST"))]),
    ),
}


def stage(quest):
    """'unowned' until the Oracle grants the deed, then each letter in turn, then 'done'."""
    if not quest.at_least("granted"):
        return "unowned"

    index = quest.progress["letter"]

    return LETTER_ORDER[index] if index < len(LETTER_ORDER) else "done"


def current_letter(quest):
    letter_id = stage(quest)

    return (letter_id, LETTERS[letter_id]) if letter_id in LETTERS else (None, None)


def policy(quest):
    """The door's policy, or None while the route is still public."""
    rules = quest.progress["house_rules"]

    return None if rules is None else [DEED_RULE] + rules


def route_yaml(quest):
    """The house's route as Pomerium would have it, for the sign outside and the desk."""
    door = policy(quest)
    lines = [
        "- from: https://" + data.HOST,
        "  prefix: " + HOUSE_PATH,
        "  to: http://quest.quest.svc.cluster.local:3000",
        "  pass_identity_headers: true",
    ]

    if door is None:
        return lines + ["  allow_public_unauthenticated_access: true"]

    return lines + ["  policy:"] + ppl.policy_yaml(door, 4)


def identity_of(quest, caller):
    if caller == "you":
        return quest.session

    if caller == "slime":
        return ANONYMOUS

    visitor = VISITORS[caller]

    return ppl.identity(True, visitor["email"], visitor["groups"])


def name_of(caller):
    if caller == "you":
        return "You"

    if caller == "slime":
        return "A slime bot"

    name = VISITORS[caller]["name"]

    return "The " + name[4:] if name.startswith("the ") else name


def allows(door, identity, request_method):
    """A public route lets in every request; otherwise the door's policy decides."""
    return True if door is None else ppl.decide(door, identity, request_method)[0]


def knock(quest, caller, request_method="GET"):
    """One knock on the door, decided and logged the way Pomerium would. True when it opens."""
    identity = identity_of(quest, caller)
    allowed = allows(policy(quest), identity, request_method)
    who = identity["email"] if identity["authenticated"] else "anonymous (a slime bot)"
    quest.record("ALLOW" if allowed else "DENY", request_method, HOUSE_PATH + "knock", who)

    return allowed


def solves(letter, rules, owner):
    """Which of the letter's visits the rules get wrong, as (caller, method, wanted) tuples."""
    door = [DEED_RULE] + rules
    wrong = []

    for visit in letter["expect"]:
        caller = visit["who"]
        identity = owner if caller == "you" else identity_of(None, caller)

        if allows(door, identity, visit["method"]) != visit["allowed"]:
            wrong.append((caller, visit["method"], visit["allowed"]))

    return wrong


def missed(caller, request_method, wanted):
    knocking = " knocking (a POST)" if request_method == "POST" else ""
    got = "were kept out" if caller == "you" else "was kept out"

    if not wanted:
        got = "got in"

    return name_of(caller) + knocking + " " + got + ", but the letter wants them " + (
        "let in." if wanted else "kept out."
    )


# What the player sees


def read_sign(g):
    public = g.quest.progress["house_rules"] is None
    text = (
        "Your door is a route left wide open with allow_public_unauthenticated_access, so Pomerium lets in every "
        "request, signed in or not. In a policy, the same thing is written accept: true. The rules you choose at "
        "the desk replace it. A route with no rules at all would let no one in."
        if public
        else "Your door is a route, and its policy is the rules you chose at the desk."
    )
    g.say(
        [
            page("Sign: Your house", text),
            page("Route: Your house", "", route_yaml(g.quest), [link("publicRoute"), link("writePolicy")]),
        ]
    )


def read_table(g, left, whole):
    """The table, by how much of the loaf is left."""
    text = "What's left of a loaf. Someone has clearly been at it."

    if left == whole:
        text = "A fresh loaf of bread."

    if left == 0:
        text = "Crumbs. The traveler was thorough."

    g.say([page("Table", text)])


def door_refuses_you(g):
    g.say(
        [
            page(
                "Your door",
                "Your door won't open for you. The rule that lets in the deed's owner needs the deed in your "
                "session. Talk to the Oracle at his temple: he can sign you in again so your session carries it.",
                links=[link("refresh")],
            )
        ]
    )


def option_pages(letter_id):
    """Each choice at the desk, with the door policy it would put on the route."""
    return [(label, ppl.policy_yaml([DEED_RULE] + rules)) for label, rules in OPTIONS[letter_id]]


def use_desk(g):
    """Reads the letter on the desk, then offers the door rules to choose from."""
    letter_id, letter = current_letter(g.quest)

    if not letter:
        g.say([page("Desk", "No letters today. Your door rules are just how you want them.")])

        return

    def chosen(index):
        label, rules = OPTIONS[letter_id][index]
        g.quest.update(house_rules=rules)
        g.rules_saved()
        learn(g, "writePolicy")
        g.toast("Your door now has the rules: " + label, "allow")
        check_letter(g, letter_id, letter)

    g.say(
        [page("Letter: " + letter["title"], letter["text"])],
        lambda: g.pick("Choose your door rules", option_pages(letter_id), chosen),
    )


def check_letter(g, letter_id, letter):
    """Everyone the letter names knocks. It's solved when the door answers each the way it asks."""
    quest = g.quest

    for visit in letter["expect"]:
        knock(quest, visit["who"], visit["method"])

    who = "Letter: " + letter["title"]
    wrong = solves(letter, quest.progress["house_rules"], quest.session)

    if any(caller == "you" and wanted for caller, _, wanted in wrong) and not quest.session["deed"]:
        door_refuses_you(g)

        return

    if wrong:
        text = "Not quite. " + " ".join(missed(*visit) for visit in wrong) + " Choose again at the desk."
        g.say([page(who, text)])

        return

    uses_deny = any(rule["action"] == "deny" for rule in quest.progress["house_rules"])

    if letter.get("needsDeny") and not uses_deny:
        g.say([page(who, "The right visitors got in, but this letter wants a deny rule.")])

        return

    def solved():
        quest.update(letter=quest.progress["letter"] + 1)
        learn(g, letter["lesson"])

        if stage(quest) == "done":
            g.toast("That's every letter. Your house is all yours.", "allow")

    g.say([page(who, letter["solved"])], solved)
