# What happens when the player talks, reads or asks a guard to let them through a gate. A port of the
# browser game's story.ts: the words are the same, but where the browser asks the real Pomerium, the badge
# decides with the policy evaluator in ppl.py.
#
# Every function here takes `g`, the game, and calls only these on it:
#   g.quest                       the Quest (quest.py)
#   g.say(pages, then=None)       show dialog pages, then call `then`
#   g.ask(pages, choices)         dialog whose last page offers choices: [(label, callback), ...]
#   g.deny(view, then=None)       show the denial screen
#   g.toast(text, tone="info")    a short message ("info", "allow" or "deny")
#   g.oracle_beside(shown)        the Oracle appears beside the player, or leaves
#   g.finale() / g.phished()      the quest's two endings

import data
import ppl
from quest import MAX_HP

GROUPS = data.GROUPS
LESSONS = data.LESSONS
ZONES = {zone["id"]: zone for zone in data.ZONES}
VISITORS = data.VISITORS
KNIGHT_QUOTA = data.KNIGHT_QUOTA

#: The address a phish's sign-in page lives at: close to the kingdom's, and not it.
PHISH_DOMAIN = "game-login.net"

#: The town fountain restores half a heart per drink, up to two full hearts each game. So do the ponds.
FOUNTAIN_LIMIT = 4
FISH_LIMIT = 4


def page(who, text, code=None, links=()):
    return {"who": who, "text": text, "code": code, "links": tuple(links)}


def link(lesson):
    return LESSONS[lesson]["link"]


def learn(g, lesson):
    if g.quest.learn(lesson):
        g.toast("Lesson learned: " + LESSONS[lesson]["title"], "allow")


def townsperson(visitor_id):
    visitor = VISITORS[visitor_id]

    return ppl.identity(True, visitor["email"], visitor["groups"])


TRAVELER = townsperson("traveler")
BAKER = townsperson("baker")


def who_of(identity):
    return identity["email"] if identity["authenticated"] else "anonymous"


def request_line(method, path):
    return method + " https://" + data.HOST + path


def claims_code(identity):
    """The session's claims, as the identity provider's token would carry them."""
    groups = identity["groups"]
    lines = ["{", '  "email": "' + identity["email"] + '",', '  "email_verified": true,']

    if groups:
        lines.append('  "groups": [')
        lines.extend('    "' + group + '"' + ("," if index < len(groups) - 1 else "") for index, group in enumerate(groups))
        lines.append("  ]" + ("," if identity["deed"] else ""))
    else:
        lines.append('  "groups": []' + ("," if identity["deed"] else ""))

    if identity["deed"]:
        lines.append('  "deed": "' + identity["deed"] + '"')

    lines.append("}")

    return lines


def is_citizen(identity):
    return GROUPS["citizens"] in identity["groups"]


# Gates


NOT_A_CITIZEN = (
    "Every allow rule needs claim/groups: "
    + GROUPS["citizens"]
    + ", and the groups claim in your session doesn't include it. When no rule matches, Pomerium denies the request."
)


def keep_refusal(g, identity):
    """The Royal Keep checks three things at once; say which ones the player still lacks."""
    vouched = g.quest.oracle_groups()
    missing = []

    if not is_citizen(identity):
        missing.append("a citizen (the Oracle can make you one)")

    if GROUPS["knights"] not in identity["groups"]:
        missing.append(
            "carrying your knight's papers (the Oracle can sign you in again at his temple)"
            if GROUPS["knights"] in vouched
            else "a knight (the Captain in the Knights' Guild can vouch for you)"
        )

    if GROUPS["scholars"] not in identity["groups"]:
        missing.append(
            "carrying your scholar's papers (the Oracle can sign you in again at his temple)"
            if GROUPS["scholars"] in vouched
            else "a scholar (read every book in the library, then talk to the Librarian)"
        )

    return (
        "Knights who are scholars only",
        'The guard of the Royal Keep reads your papers twice. "My orders: only knights who are also scholars. '
        + "You still need to be "
        + ", and ".join(missing)
        + '."',
        "The keep's one rule needs claim/groups: citizens, claim/groups: knights and claim/groups: scholars. "
        "In an and rule every check must pass; the X lines are the ones your session fails.",
    )


def citizens_only(place, identity):
    return (
        "Citizens only",
        'The guard lowers a spear across the road. "'
        + place
        + " is for citizens. Those are my orders. Your papers say "
        + identity["email"]
        + ', but nothing in them says citizen, so I can\'t let you pass."',
        NOT_A_CITIZEN,
    )


def refusal(g, zone, identity):
    """Why a guard refused, as the kingdom sees it and as Pomerium decided it: (title, story, hint)."""
    zone_id = zone["id"]

    if zone_id == "town":
        return citizens_only("The town", identity)

    if zone_id == "guild":
        return citizens_only("The Knights' Guild", identity)

    if zone_id == "library":
        return citizens_only("The library", identity)

    if zone_id == "armory":
        return (
            "Knights only",
            "The guard doesn't budge. \"My orders say knights only, and nothing in your papers says knight. "
            'The Captain in the Knights\' Guild can vouch for you."',
            "The armory's only rule needs claim/groups: knights, and the groups claim in your session "
            "doesn't include knights.",
        )

    if zone_id == "keep":
        return keep_refusal(g, identity)

    if zone_id == "scriptorium":
        if not is_citizen(identity):
            return citizens_only("The scriptorium", identity)

        return (
            "Scribes only",
            'The scriptorium guard bars the door. "This room is for writing in the Royal Ledger, and my orders '
            'say only scribes may come in. Your papers say you may read, not write."',
            "The scriptorium's path, "
            + zone["prefix"]
            + ", is inside the library's, so Pomerium matched this more specific route and checked its policy "
            "instead. Its only rule needs claim/groups: scribes, and the groups claim in your session doesn't "
            "include scribes. No rule matched, so Pomerium denied it. This denial is the lesson.",
        )

    return (
        "The guard won't let you pass",
        '"Sorry, my orders don\'t cover you."',
        "No allow rule matched this request, so Pomerium denied it.",
    )


def deny_view(g, zone, method, path, identity, sign_in):
    _, lines = ppl.decide(zone["policy"], identity, method)

    if sign_in:
        return {
            "status": 401,
            "title": "Sign in required",
            "story_title": "The guard doesn't know you",
            "story": 'The guard holds out a hand. "Papers, please. My orders are to let in only people the Oracle '
            'has vouched for, and you have no papers at all. His temple is back in Hearth Village."',
            "request": request_line(method, path),
            "who": "anonymous",
            "lines": lines,
            "hint": "You have no session yet. Pomerium sends anyone without one to the identity provider to sign "
            "in, then back here. Visit the Oracle in his temple back in Hearth Village.",
            "links": (link("idp"), link("authz")),
        }

    title, story, hint = refusal(g, zone, identity)

    return {
        "status": 403,
        "title": "Access denied",
        "story_title": title,
        "story": story,
        "request": request_line(method, path),
        "who": who_of(identity),
        "lines": lines,
        "hint": hint,
        "links": (link("authz"), link("defaultDeny")),
    }


def attempt(g, zone_id, method, action, ask_sign_in=True):
    """Decides one request the way Pomerium would, logs it, and shows the denial screen when refused.

    Returns "allow", "signin" (no session, so Pomerium would send the player to sign in) or "deny".
    """
    zone = ZONES[zone_id]
    identity = g.quest.session
    path = zone["prefix"] + "/" + action
    allow, _ = ppl.decide(zone["policy"], identity, method)

    if allow:
        g.quest.record("ALLOW", method, path, who_of(identity))

        return "allow"

    if not identity["authenticated"]:
        g.quest.record("SIGN IN", method, path, "anonymous")

        if ask_sign_in:
            g.deny(deny_view(g, zone, method, path, identity, True))

        return "signin"

    g.quest.record("DENY", method, path, who_of(identity))

    def after():
        learn(g, "authz")

        if zone_id == "keep":
            learn(g, "allOf")

    g.deny(deny_view(g, zone, method, path, identity, False), after)

    return "deny"


def enter_gate(g, zone_id, leaving=False):
    """Asks a gate's route to let the player through with a GET to enter."""
    outcome = attempt(g, zone_id, "GET", "enter", not leaving)

    if outcome != "allow":
        return outcome

    zone = ZONES[zone_id]
    g.toast("ALLOW  GET " + zone["prefix"] + "/enter", "allow")
    learn(g, "every")
    learn(g, "route")

    if zone_id in ("armory", "library"):
        learn(g, "jwt")

    if zone_id == "keep":
        learn(g, "allOf")
        g.finale()

    return "allow"


def read_sign(g, zone_id):
    """A gate's sign: its own words, then the route config of the zone the gate asks."""
    zone = ZONES[zone_id]
    pages = [
        page("Sign: " + zone["name"], data.SIGN_TEXT.get(zone_id, "")),
        page("Route: " + zone["name"], "", data.ROUTE_YAML[zone_id], data.SIGN_DOCS.get(zone_id, ())),
    ]
    g.say(pages, lambda: learn(g, "route"))


# The Oracle


SAGE_HINT = page("Oracle", "Before you go anywhere, speak with the sage. They have news for you.")


def citizenship_pages():
    return [
        page(
            "Oracle",
            "The sage told you. Every newcomer is entitled to be a citizen, and a citizen to a house outside the "
            "walls. Yours is in the Slime Fields, just below the pond. I have added two claims to your papers: "
            "the group citizen, and a deed claim that names your house.",
            links=[link("claims")],
        ),
        page(
            "Oracle",
            "The guards in town check for citizen. Your house door is a Pomerium route like every gate in the "
            "kingdom, but you write its rules, and whoever holds the deed always gets in. The builders left it "
            "wide open, with allow_public_unauthenticated_access: everyone gets in, even with no session at "
            "all. I hear the slimes have noticed.",
            links=[link("publicRoute")],
        ),
    ]


def refresh_page(g):
    return page(
        "Oracle",
        "Pomerium decides with the claims in your session, and those are the ones I gave you when you signed "
        "in. It refreshes them from me now and then, but that can take a while. Let me sign you in again so "
        "your session carries the new one now.",
        links=[link("refresh")],
    )


def welcome_back(g, then=None):
    g.say(
        [
            page(
                "Oracle",
                "Signed in again. Your new claims are below. Every guard reads them from now on.",
                claims_code(g.quest.session),
            )
        ],
        then,
    )


def refresh_claims(g, then=None):
    """Signs the player in again so their session carries the groups the Oracle has added since."""
    g.quest.sign_in()
    welcome_back(g, then)


def oracle_arrives(g, letter):
    """Rather than send the player back to his temple, the Oracle appears beside them with their new claim."""
    g.oracle_beside(True)

    def then():
        learn(g, "refresh")
        refresh_claims(g, lambda: g.oracle_beside(False))

    g.say([page("Oracle", letter), refresh_page(g)], then)


def grant_citizenship(g):
    """The Oracle makes an invited newcomer a citizen and grants their deed, then signs them in again."""

    def then():
        learn(g, "refresh")
        g.quest.send("CITIZEN_GRANTED")
        g.toast("The Oracle added the deed to your house", "allow")
        refresh_claims(g)

    g.say(
        citizenship_pages()
        + [
            page(
                "Oracle",
                "Your session still holds the claims I gave you at sign-in, so let me sign you in again. Then it "
                "will carry them.",
                links=[link("refresh")],
            )
        ],
        then,
    )


def oracle(g):
    quest = g.quest

    if not quest.session["authenticated"]:

        def signed_in():
            learn(g, "idp")
            quest.sign_in()
            pages = [
                page(
                    "Oracle",
                    "There. You are " + quest.session["email"] + ". Here are your claims.",
                    claims_code(quest.session),
                )
            ]

            if quest.stage == "newcomer":
                pages.append(SAGE_HINT)

            g.say(pages)

        g.say(
            [
                page("Oracle", "I am the Oracle. I don't guard gates. I answer one question: who is this?"),
                page(
                    "Oracle",
                    "In Pomerium terms, I am your identity provider, like Google, Okta or GitHub. Pomerium never "
                    "sees your password. It sends you to me, I check who you are, and then I give Pomerium a "
                    "signed token with your claims.",
                    links=[link("idp")],
                ),
                page("Oracle", "Step into the light and tell me who you are."),
            ],
            signed_in,
        )

        return

    if quest.stage == "newcomer":
        g.say([SAGE_HINT])

        return

    if quest.stage == "invited":
        grant_citizenship(g)

        return

    missing = quest.stale()

    if missing:

        def then():
            learn(g, "refresh")
            refresh_claims(g)

        g.say([page("Oracle", "I have added " + " and ".join(missing) + " to your claims."), refresh_page(g)], then)

        return

    g.say([page("Oracle", "These are your claims as Pomerium sees them.", claims_code(quest.session))])


# The townsfolk


def sage(g):
    quest = g.quest

    if not quest.session["authenticated"]:
        g.say(
            [
                page("Sage", "You're awake. Good. The kingdom has changed while you slept."),
                page(
                    "Sage",
                    "Our neighbors in Wallhold trusted one big wall. Once a raider got over it, every room inside "
                    "was theirs.",
                ),
                page(
                    "Sage",
                    "Here every guard checks you each time you pass. Pomerium works the same way: each request to "
                    "each app is checked against that app's policy.",
                    links=[link("every")],
                ),
                page(
                    "Sage",
                    "Bot slimes and phish roam the fields, and both mean harm. The bots hammer the town gate day "
                    "and night, but they'll never get in. They can't prove they're citizens, and the guard checks "
                    "every one of them, every time.",
                ),
                page(
                    "Sage",
                    "The phish are craftier. They don't storm the gate. They dress up as the Oracle, robes and "
                    "all, and offer to sign you in, because a guard can't tell stolen papers from yours. The real "
                    "Oracle keeps to his temple. Only ever sign in there.",
                ),
                page(
                    "Sage",
                    "Guards only let in people they can identify. Visit the Oracle in the temple to the west.",
                ),
            ],
            lambda: learn(g, "every"),
        )

        return

    if quest.stage == "newcomer":
        g.say(
            [
                page(
                    "Sage",
                    "The Oracle knows who you are. That's not the same as being a citizen: the guards in town "
                    "want to see it in your papers.",
                    links=[link("claims")],
                ),
                page(
                    "Sage",
                    "You're about to become a citizen. And every citizen is entitled to a house outside the "
                    "walls: an empty one in the Slime Fields, just below the pond.",
                ),
                page(
                    "Sage",
                    "Go and see the Oracle again. He will put two claims in your papers: a group called citizens, "
                    "and the deed to your house.",
                ),
            ],
            lambda: quest.send("SAGE_SPOKE"),
        )

        return

    if quest.stage == "invited":
        g.say(
            [
                page(
                    "Sage",
                    "Go and see the Oracle, in his temple to the west. He will put your citizens group and the "
                    "deed to your house in your papers.",
                )
            ]
        )

        return

    if quest.stage == "granted":
        g.say(
            [
                page(
                    "Sage",
                    "The Oracle has made you a citizen, but your papers still show the old claims. Visit him once "
                    "more, and he will sign you in again.",
                )
            ]
        )

        return

    g.say(
        [
            page(
                "Sage",
                "Head north through the Fields Gate. A guard stands at every gate, and the sign beside it shows "
                "the exact orders that guard follows.",
            ),
            page(
                "Sage",
                "Your house stands out in the Slime Fields, just below the pond. Nobody guards it but its own door "
                "rules, and the slimes have noticed.",
            ),
        ]
    )


def captain(g):
    quest = g.quest

    if quest.at_least("knighted"):
        text = (
            "The Oracle has your new claim, but your session still carries the old one. Visit him in the temple "
            "and sign in again, then claim your steel in the armory, east of here across the square."
            if quest.stage == "knighted"
            else "Go claim your steel. The armory is east of here, across the square."
        )
        g.say([page("Captain", text)])

        return

    if quest.stage != "proven":
        g.say(
            [
                page("Captain", "The armory is for knights only."),
                page(
                    "Captain",
                    "Bot slimes plague the fields, hammering every gate at once, never tiring. And watch for "
                    "strangers in dark robes, dressed as the Oracle. Those are phish, and no sword will help you "
                    "there.",
                ),
                page(
                    "Captain",
                    "Prove yourself: defeat %d bot slimes, then come back. So far: %d of %d."
                    % (KNIGHT_QUOTA, min(quest.defeated, KNIGHT_QUOTA), KNIGHT_QUOTA),
                ),
            ]
        )

        return

    if attempt(g, "guild", "POST", "knight") != "allow":
        return

    quest.send("KNIGHTED")

    def then():
        learn(g, "claims")
        oracle_arrives(g, "The Captain's letter arrived. I've added knights to your groups.")

    g.say(
        [
            page("Captain", "Well fought. I've written to the Oracle: from now on you are in the knights group."),
            page(
                "Captain",
                "Notice what changed. Not the armory: its policy is the same as yesterday. Your identity changed. "
                "The Oracle now lists you in groups: [knights].",
            ),
            page(
                "Captain",
                "Pomerium reads groups from your identity provider. It doesn't decide who is a knight. It checks "
                "the claim.",
                links=[link("claims")],
            ),
            page(
                "Captain",
                "One catch: your session still holds the claims from when you signed in, so your groups don't say "
                "knights yet. Pomerium would catch up on its own in time, but you needn't wait. Ah, here comes the "
                "Oracle.",
            ),
        ],
        then,
    )


def traveler(g):
    town = ZONES["town"]
    path = town["prefix"] + "/enter"

    def then():
        g.quest.record("DENY", "GET", path, TRAVELER["email"])
        _, lines = ppl.decide(town["policy"], TRAVELER, "GET", "their")
        g.deny(
            {
                "status": 403,
                "title": "Access denied",
                "on_behalf_of": "the Traveler",
                "story_title": "Not a citizen",
                "story": "The town guard turns the Traveler away. The Oracle knows them as "
                + TRAVELER["email"]
                + ", but the town only opens to citizens.",
                "request": request_line("GET", path),
                "who": TRAVELER["email"],
                "lines": lines,
                "hint": "Their groups claim has no citizen in it, and only citizens may enter. This was the "
                "Traveler's request: your own access hasn't changed.",
                "links": (link("authz"), link("defaultDeny")),
            },
            lambda: learn(g, "authz"),
        )

    g.say(
        [
            page("Traveler", "The Oracle knows me. I'm " + TRAVELER["email"] + ", signed in and everything."),
            page(
                "Traveler",
                "But this town only lets in citizens, and the Oracle hasn't made me one. Signing in got me as far "
                "as the guard. It didn't get me past them.",
            ),
            page("Traveler", "Signing in says who you are. Policy says where you can go.", links=[link("authz")]),
        ],
        then,
    )


def baker(g):
    """The Traveler's counterpart: same guard, same orders, but this citizen gets in."""
    path = ZONES["town"]["prefix"] + "/enter"

    def then():
        g.quest.record("ALLOW", "GET", path, BAKER["email"])
        g.toast("ALLOW  GET " + path + " as " + BAKER["email"], "allow")
        learn(g, "authz")

    g.say(
        [
            page("Baker", "Morning! I'm " + BAKER["email"] + ". I bring bread in through the town gate every day."),
            page(
                "Baker",
                "The guard checks me every single time, same as everyone. My groups claim says citizen, so I match "
                "the guard's orders and I'm let through.",
            ),
            page(
                "Baker",
                "The Traveler outside faces the same guard and the same orders. The only difference is who we are.",
                links=[link("authz")],
            ),
        ],
        then,
    )


ARMORER_INTRO = (
    "I forge the blades. I don't decide who gets in: the guard does. The guard checks your claims on every "
    "visit. Their orders are on the sign: only the knights group."
)

ARMORER = {
    "proven": ARMORER_INTRO + " The Captain can vouch for you.",
    "knighted": "The Oracle lists you as a knight? Then your session hasn't caught up. The guard reads the claims "
    "in your session, and those were set when you signed in. Pomerium refreshes them from the Oracle now and "
    "then, but sign in with him again and you won't have to wait.",
    "knight": "Your session says groups: [knights] now, so the guard will let you through. The steel sword is in "
    "the chest inside.",
    "armed": "Same guard, same orders as before you were a knight. You didn't unlock a policy. You gained the "
    "claim it was waiting for.",
}


def armorer(g):
    text = ARMORER.get(g.quest.stage, ARMORER_INTRO)
    g.say([page("Armorer", text, links=[link("onroute")] if g.quest.has_steel() else ())])


LIBRARIAN_INTRO = [
    page(
        "Librarian",
        "Read anything you like. The guard at the front door still checks every request, even now that you're "
        "inside. Opening a book sends a GET to the library, and the guard checks it again.",
    ),
    page(
        "Librarian",
        "My shelves are for reading only. The library's rule lets citizens send a GET, which reads, and nothing "
        "else. A rule can check the request itself, not just who sent it.",
        links=[link("request")],
    ),
    page(
        "Librarian",
        "The Royal Ledger is next door, in the scriptorium. Its path is inside the library's, but it's a route of "
        "its own, with a guard who follows its own rule: scribes only. Go ahead and try: the denial will show "
        "you which rule failed.",
    ),
    page(
        "Librarian",
        "And no, I can't make you a scribe. No one in the kingdom can yet. The point is to watch the rule that "
        "fails.",
    ),
]


def librarian(g):
    quest = g.quest
    progress = quest.progress
    books = len(data.BOOKS)

    if progress["scholar"]:
        g.say(
            [
                page(
                    "Librarian",
                    "The Royal Keep lies at the end of the road that runs south, just west of the library. Its "
                    "guard wants citizens who are knights and scholars, and checks all three at once.",
                )
            ]
        )

        return

    left = books - len(progress["books_read"])

    if left > 0:
        g.say(
            LIBRARIAN_INTRO
            + [
                page(
                    "Librarian",
                    "I can make you a scholar, though. Scholars read; scribes write. Read every book on my shelves "
                    "and come back: %d of %d to go." % (left, books),
                )
            ],
            lambda: learn(g, "request"),
        )

        return

    if attempt(g, "oracle", "POST", "scholar") != "allow":
        return

    quest.update(scholar=True)
    g.say(
        [
            page(
                "Librarian",
                "You've read every book on my shelves. I've written to the Oracle: from now on you are in the "
                "scholars group.",
            ),
            page(
                "Librarian",
                "Scholars read and scribes write, so the ledger still won't take your pen. But the Royal Keep, down "
                "the road southwest of here, wants knights who are scholars too.",
                links=[link("claims")],
            ),
        ],
        lambda: oracle_arrives(g, "The Librarian's letter arrived. I've added scholars to your groups."),
    )


SCRIPTS = {
    "sage": sage,
    "oracle": oracle,
    "traveler": traveler,
    "baker": baker,
    "captain": captain,
    "armorer": armorer,
    "librarian": librarian,
}


def talk(g, npc_id):
    SCRIPTS[npc_id](g)


# Phish, the chest, books and the rest of the kingdom


def meet_phish(g, on_turned_away):
    """A phish, dressed as the Oracle, offers to sign the player in. Accepting loses the game."""

    def accept():
        g.say([page("Oracle?", "Thank you kindly. Heh. Heh heh heh...")], g.phished)

    def refuse():
        g.say(
            [
                page("Oracle?", "Hmph. Suit yourself. The robe slips as it turns away: no beard, just scales."),
                page(
                    "Pomerium Quest",
                    "That was a phish. The real Oracle never comes looking for your password, and his page is never "
                    "at " + PHISH_DOMAIN + ". Only ever sign in with your real identity provider.",
                    links=[link("idp")],
                ),
            ],
            on_turned_away,
        )

    g.ask(
        [
            page(
                "Oracle?",
                "Ah, there you are! I am the Oracle. Your session is about to expire, and then every guard will "
                "turn you away. Quick, there's no time to walk back to the temple.",
            ),
            page(
                "Oracle?",
                "Just sign in with me right here. My page is at oracle."
                + PHISH_DOMAIN
                + ". Your email and password, that's all I need.",
            ),
        ],
        [("Sign in here", accept), ("No. I only sign in at the temple.", refuse)],
    )


PHISHED = [
    page(
        "You were phished!",
        "A phish in a borrowed robe asked for your sign-in, and you handed it over. Now it walks up to every guard "
        "as you, and every guard checks it and lets it in. As far as any guard can tell, the phish is you.",
    ),
    page(
        "You were phished!",
        "In Pomerium terms: Pomerium checks every request against who your identity provider says you are. "
        "Credentials typed into a fake sign-in page let someone else be you. Only sign in on your real identity "
        "provider's page, check its address, and prefer sign-ins a fake page can't replay, like passkeys.",
        links=[link("idp")],
    ),
]


def open_chest(g):
    """True when the player takes the steel sword."""
    if g.quest.stage != "knight":
        return False

    g.quest.send("STEEL_TAKEN")
    g.say(
        [
            page("Armory", "You found the Steel Sword! Strong enough to break cracked rock."),
            page(
                "Armory",
                "In Pomerium the policy lives on the route. People don't carry policies around. They carry "
                "identity, and each route decides.",
                links=[link("onroute")],
            ),
        ],
        lambda: learn(g, "onroute"),
    )

    return True


def read_book(g, index):
    books = data.BOOKS
    which = index % len(books)

    if attempt(g, "library", "GET", "books/%d" % index) != "allow":
        return

    book = books[which]
    progress = g.quest.progress
    first_read = which not in progress["books_read"]

    if first_read:
        g.quest.update(books_read=progress["books_read"] + [which])

    def then():
        lesson = book["links"][0] if book["links"] else None

        for lesson_id in data.LESSON_ORDER:
            if LESSONS[lesson_id]["link"] == lesson:
                learn(g, lesson_id)

        if first_read and not progress["scholar"] and len(g.quest.progress["books_read"]) == len(books):
            g.toast("You've read every book. The Librarian would like a word.")

    g.say([page(book["who"].replace("·", ":"), book["text"], links=book["links"])], then)


def hearts(halves):
    whole = halves // 2

    if halves % 2 == 0:
        return "%d %s" % (whole, "heart" if whole == 1 else "hearts")

    return "%d and a half hearts" % whole if whole else "half a heart"


def drink_from_fountain(g):
    quest = g.quest
    left = FOUNTAIN_LIMIT - quest.progress["fountain_healed"]

    def say(text):
        g.say([page("Town Fountain", text)])

    if quest.hp >= MAX_HP:
        say("Cool, fresh water. You're already at full health.")

        return

    if left <= 0:
        say("The water still runs, but it can't restore any more hearts this game.")

        return

    quest.set_hp(quest.hp + 1)
    quest.update(fountain_healed=quest.progress["fountain_healed"] + 1)
    say(
        "You drink the cool water and feel a little better: half a heart restored. The fountain has %s left to "
        "give this game." % hearts(left - 1)
        if left > 1
        else "You drink the cool water and feel a little better: half a heart restored. That's all the fountain "
        "can give this game."
    )


def eat_fish(g):
    """Eats a caught fish if it would help. Returns False to leave the fish in the pond."""
    quest = g.quest
    left = FISH_LIMIT - quest.progress["fish_eaten"]

    def say(text):
        g.say([page("Pond", text)])

    if quest.hp >= MAX_HP:
        say("A fish darts past. You're already at full health, so you let it be.")

        return False

    if left <= 0:
        say("The fish are wise to you now. You can't catch any more this game.")

        return False

    quest.set_hp(quest.hp + 1)
    quest.update(fish_eaten=quest.progress["fish_eaten"] + 1)
    say(
        "You catch a fish and gulp it down: half a heart restored. The ponds have %s left to give this game."
        % hearts(left - 1)
        if left > 1
        else "You catch a fish and gulp it down: half a heart restored. That's all the ponds can give this game."
    )

    return True


def read_anvil(g):
    g.say(
        [
            page(
                "Anvil",
                "A heavy iron anvil, its face worn bright by years of hammering. Every blade in the kingdom was "
                "shaped here. Forging a sword never decided who may carry it past the guard.",
            )
        ]
    )


def read_workbench(g):
    g.say(
        [
            page(
                "Workbench",
                "Hammers, tongs and a whetstone, laid out in neat rows. They belong to the Armorer, and you're only "
                "here to look.",
            )
        ]
    )


INTRO = [
    page(
        "Pomerium Quest",
        "Move with Up, Down, Left and Right. Walk into a sign, a person or a chest to read, talk or open it. "
        "Press Select to swing your sword, and Select again to go on through a talk. Press Menu for your journal.",
    ),
    page("Pomerium Quest", "The sage in the house to your right has been waiting for you. Go say hello."),
]


FINALE = [
    page(
        "The Royal Keep",
        "The guard reads your papers: citizens, knights, scholars. Every check in the keep's one rule passes, and "
        "the doors swing open. You did it!",
    ),
    page(
        "The Royal Keep",
        "Along the way, nothing about the gates changed. Your identity did: the Oracle vouched for you, your "
        "session carried the claims, and each guard checked them against its own route's policy, on every "
        "request. That's Pomerium.",
        links=[link("allOf")],
    ),
]
