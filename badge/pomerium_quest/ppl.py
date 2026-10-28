# A port of Pomerium Quest's PPL evaluator (app/src/game/ppl.ts). On the badge it stands in for Pomerium:
# it decides each request and explains which line passed and which failed. tests/test_ppl.py checks it
# against the browser game's own decisions.

YAML_WORDS = ("true", "false", "null", "yes", "no", "on", "off", "y", "n", "~")


def claim_value(claim, value):
    """A claim value as YAML reads it: quoted when it could pass for a number, boolean or null."""
    looks_typed = value[:1] in "-+.0123456789" and value != "" or value.lower() in YAML_WORDS

    return '"' + value + '"' if claim == "deed" or looks_typed else value


def criterion_label(node):
    """A criterion on one line, as the denial screen shows it."""
    kind = node["kind"]

    if kind == "accept":
        return "accept: true"

    if kind == "authenticated_user":
        return "authenticated_user: true"

    if kind == "claim":
        return "claim/" + node["claim"] + ": " + claim_value(node["claim"], node["value"])

    return kind + ": { is: " + node["is"] + " }"


def criterion_yaml(node):
    """The YAML lines Pomerium reads for one criterion."""
    kind = node["kind"]

    if kind in ("domain", "email", "http_method"):
        return [kind + ":", "  is: " + node["is"]]

    return [criterion_label(node)]


def policy_yaml(policy, indent=0):
    """A policy as YAML lines, starting at `indent`."""
    pad = " " * indent
    lines = []

    for rule in policy:
        lines.append(pad + "- " + rule["action"] + ":")
        lines.append(pad + "    " + rule["match"] + ":")

        for node in rule["criteria"]:
            first, *rest = criterion_yaml(node)
            lines.append(pad + "      - " + first)
            lines.extend(pad + "        " + line for line in rest)

    return lines


def identity(authenticated=False, email="", groups=(), deed=None):
    """A session as Pomerium sees it: who signed in, and the claims their identity provider gave them."""
    return {"authenticated": authenticated, "email": email, "groups": tuple(groups), "deed": deed}


def claim_values(claim, who):
    if claim == "groups":
        return list(who["groups"])

    if claim == "email":
        return [who["email"]]

    return [who["deed"]] if who.get("deed") else []


def check(node, who, method, whose):
    """Whether one criterion matches, and what the session actually held."""
    kind = node["kind"]
    email = who["email"]
    domain = email.split("@")[1] if "@" in email else ""

    if kind == "accept":
        return True, "every request matches"

    if kind == "authenticated_user":
        signed_in = who["authenticated"]
        actual = ("you are" if whose == "your" else "they are") + " signed in" if signed_in else "no session"

        return signed_in, actual

    if kind == "domain":
        return domain == node["is"], whose + " domain: " + (domain or "none")

    if kind == "email":
        return email == node["is"], whose + " email: " + (email or "none")

    if kind == "http_method":
        return method == node["is"], "this request: " + method

    values = claim_values(node["claim"], who)

    return node["value"] in values, whose + " " + node["claim"] + ": [" + ", ".join(values) + "]"


COMBINE = {
    "and": all,
    "or": any,
    "not": lambda results: not any(results),
}


def decide(policy, who, method="GET", whose="your"):
    """Allowed when an allow rule matches and no deny rule does; with no matching allow rule, denied.

    Returns (allow, lines). Each line is a dict with `text`, and criteria lines also carry `ok` and `actual`.
    """
    lines = []
    matched = {"allow": False, "deny": False}

    for rule in policy:
        results = []
        lines.append({"text": "- " + rule["action"] + ":"})
        lines.append({"text": "    " + rule["match"] + ":"})

        for node in rule["criteria"]:
            ok, actual = check(node, who, method, whose)
            results.append(ok)
            lines.append({"text": "      - " + criterion_label(node), "ok": ok, "actual": actual})

        if COMBINE[rule["match"]](results):
            matched[rule["action"]] = True

    return matched["allow"] and not matched["deny"], lines
