# Everything drawn over the kingdom: the HUD, toasts, dialogs, the denial screen, the desk and the journal.
# Uses the badge firmware's builtins (screen, color, font, shape, vec2), so it only runs on the badge.

WIDTH = screen.width
HEIGHT = screen.height

# Colours from the browser game's night-and-sunset palette.
NIGHT = color.rgb(20, 17, 31)
NIGHT_DEEP = color.rgb(11, 9, 16)
PANEL = color.rgb(20, 17, 31, 235)
SHADE = color.rgb(0, 0, 0, 170)
BORDER = color.rgb(251, 211, 166)
TEXT = color.rgb(240, 236, 250)
MUTED = color.rgb(170, 160, 210)
SUN = color.rgb(239, 143, 85)
LIME = color.rgb(200, 255, 40)
PINK = color.rgb(255, 79, 184)
RED = color.rgb(255, 93, 115)
CODE = color.rgb(143, 220, 255)
HEART = color.rgb(255, 79, 120)
HEART_EMPTY = color.rgb(70, 60, 90)

TONES = {"info": SUN, "allow": LIME, "deny": RED}

BODY = font.sins
TITLE = font.smart
LINE = 12
PAD = 8

#: Characters the pixel fonts lack, and what to draw instead.
PLAIN = {
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "·": ":",
    "…": "...",
    "—": "-",
    "–": "-",
    "½": " and a half",
}

_wrapped = {}


def plain(text):
    for fancy, simple in PLAIN.items():
        if fancy in text:
            text = text.replace(fancy, simple)

    return text


def wrap(text, width, face=BODY):
    """Splits text into lines that fit `width`, remembering the answer since measuring is slow."""
    key = (text, width, id(face))
    lines = _wrapped.get(key)

    if lines is not None:
        return lines

    screen.font = face
    lines = []

    for paragraph in plain(text).split("\n"):
        line = ""

        for word in paragraph.split(" "):
            candidate = word if not line else line + " " + word

            if screen.measure_text(candidate)[0] <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word

        lines.append(line)

    if len(_wrapped) > 200:
        _wrapped.clear()

    _wrapped[key] = lines

    return lines


def text(words, x, y, pen=TEXT, face=BODY):
    screen.font = face
    screen.pen = pen
    screen.text(words, x, y)


def centred(words, y, pen=TEXT, face=BODY):
    screen.font = face
    width = screen.measure_text(words)[0]
    text(words, (WIDTH - width) // 2, y, pen, face)


def box(x, y, w, h, fill=PANEL, edge=BORDER):
    screen.pen = edge
    screen.shape(shape.rounded_rectangle(x, y, w, h, 4))
    screen.pen = fill
    screen.shape(shape.rounded_rectangle(x + 2, y + 2, w - 4, h - 4, 3))


def code(lines, x, y, pen=CODE):
    """Code keeps its indentation: each leading space moves the line a fixed step right."""
    screen.font = BODY
    step = 4

    for line in lines:
        stripped = line.lstrip(" ")
        text(stripped, x + (len(line) - len(stripped)) * step, y, pen)
        y += LINE

    return y


def prompt(x, y, ticks, pen=LIME):
    """A small blinking arrow that says Select goes on."""
    if (ticks // 400) % 2:
        return

    screen.pen = pen
    screen.shape(shape.regular_polygon(x, y, 4, 3, 1.5708))


def mark(ok, x, y):
    """A tick or a cross, drawn rather than typed, since the fonts have neither."""
    screen.pen = LIME if ok else RED

    if ok:
        screen.shape(shape.line(x, y + 4, x + 3, y + 7, 2))
        screen.shape(shape.line(x + 3, y + 7, x + 8, y + 1, 2))
    else:
        screen.shape(shape.line(x + 1, y + 1, x + 7, y + 7, 2))
        screen.shape(shape.line(x + 7, y + 1, x + 1, y + 7, 2))


def heart(x, y, fill):
    """A heart: `fill` is 0 (empty), 1 (half) or 2 (full)."""
    screen.pen = HEART_EMPTY
    screen.shape(shape.circle(x + 3, y + 3, 3))
    screen.shape(shape.circle(x + 8, y + 3, 3))
    screen.shape(shape.regular_polygon(x + 5.5, y + 6, 5.5, 3, 1.5708))

    if fill == 0:
        return

    screen.pen = HEART
    screen.shape(shape.circle(x + 3, y + 3, 3))
    screen.shape(shape.regular_polygon(x + 5.5, y + 6, 5.5, 3, 1.5708) if fill == 2 else shape.circle(x + 3, y + 5, 2))

    if fill == 2:
        screen.shape(shape.circle(x + 8, y + 3, 3))


def hud(hp, max_hp, region):
    screen.pen = SHADE
    screen.rectangle(0, 0, WIDTH, 16)

    for index in range(max_hp // 2):
        heart(4 + index * 13, 3, max(0, min(2, hp - index * 2)))

    screen.font = BODY
    width = screen.measure_text(region)[0]
    text(region, WIDTH - width - 6, 2, MUTED)


def toast(message, tone):
    lines = wrap(message, WIDTH - 32)[:3]
    height = len(lines) * LINE + 8
    box(8, 20, WIDTH - 16, height, PANEL, TONES.get(tone, SUN))
    y = 24

    for line in lines:
        text(line, 16, y, TEXT)
        y += LINE


# Dialog


DIALOG_Y = 128
DIALOG_H = HEIGHT - DIALOG_Y - 4
DIALOG_LINES = (DIALOG_H - 34) // LINE
CODE_LINES = (HEIGHT - 52) // LINE


def screens_of(page_):
    """A page split into what fits on screen at once: text in the dialog box, code on a full panel."""
    parts = []
    lines = wrap(page_["text"], WIDTH - 2 * PAD - 8) if page_["text"] else []

    for start in range(0, len(lines), DIALOG_LINES):
        parts.append({"kind": "text", "who": page_["who"], "lines": lines[start : start + DIALOG_LINES]})

    code_lines = page_.get("code") or []

    for start in range(0, len(code_lines), CODE_LINES):
        parts.append({"kind": "code", "who": page_["who"], "lines": code_lines[start : start + CODE_LINES]})

    if parts:
        parts[-1]["links"] = page_.get("links") or ()

    return parts or [{"kind": "text", "who": page_["who"], "lines": [], "links": ()}]


def docs_line(links):
    return "Docs: " + ", ".join(entry["label"] for entry in links) if links else ""


def dialog(part, ticks, last):
    if part["kind"] == "code":
        box(4, 4, WIDTH - 8, HEIGHT - 8, color.rgb(11, 9, 16, 245))
        text(plain(part["who"]), PAD + 4, PAD + 2, SUN, TITLE)
        code(part["lines"], PAD + 4, PAD + 26)
    else:
        box(4, DIALOG_Y, WIDTH - 8, DIALOG_H)
        text(plain(part["who"]), PAD + 4, DIALOG_Y + 6, SUN)
        y = DIALOG_Y + 20

        for line in part["lines"]:
            text(line, PAD + 4, y)
            y += LINE

    docs = docs_line(part.get("links"))

    if docs:
        line = wrap(docs, WIDTH - 40)[0]
        text(line, PAD + 4, HEIGHT - 20, MUTED)

    prompt(WIDTH - 18, HEIGHT - 14, ticks, LIME if not last else SUN)


def choices(options, selected, ticks):
    """The phish's offer: options to pick from with Up and Down, in the dialog box."""
    box(4, DIALOG_Y, WIDTH - 8, DIALOG_H)
    text("Choose with Up and Down, then press Select", PAD + 4, DIALOG_Y + 6, MUTED)
    y = DIALOG_Y + 26

    for index, (label, _) in enumerate(options):
        pen = LIME if index == selected else TEXT

        if index == selected:
            screen.pen = LIME
            screen.triangle(PAD + 5, y + 1, PAD + 11, y + 5, PAD + 5, y + 9)

        for line in wrap(label, WIDTH - 2 * PAD - 24):
            text(line, PAD + 18, y, pen)
            y += LINE

        y += 6


# The denial screen


def deny_parts(view):
    """The denial in three screens: the story, how Pomerium decided, and what to do about it."""
    story_lines = wrap(view["story"], WIDTH - 2 * PAD - 8)

    if view.get("on_behalf_of"):
        story_lines = ["Watching " + view["on_behalf_of"] + "'s request:"] + story_lines

    return [
        {"kind": "story", "title": view["story_title"], "lines": story_lines},
        {"kind": "decision"},
        {"kind": "hint", "lines": wrap(view["hint"], WIDTH - 2 * PAD - 8), "links": view["links"]},
    ]


def deny(view, part, ticks, last):
    box(4, 4, WIDTH - 8, HEIGHT - 8, color.rgb(11, 9, 16, 245), RED)
    status = "%d  %s" % (view["status"], view["title"])
    text(status, PAD + 4, PAD + 2, RED, TITLE)
    y = PAD + 26

    if part["kind"] == "story":
        text(plain(part["title"]), PAD + 4, y, SUN)
        y += LINE + 4

        for line in part["lines"]:
            text(line, PAD + 4, y)
            y += LINE

    elif part["kind"] == "decision":
        for line in wrap(view["request"], WIDTH - 2 * PAD - 8):
            text(line, PAD + 4, y, CODE)
            y += LINE

        text("as " + view["who"], PAD + 4, y, MUTED)
        y += LINE + 4

        for line in view["lines"]:
            stripped = line["text"].lstrip(" ")
            indent = (len(line["text"]) - len(stripped)) * 4

            if "ok" in line:
                mark(line["ok"], PAD + 4, y + 2)
                text(stripped, PAD + 16 + indent, y, CODE)
                y += LINE
                text(line["actual"], PAD + 28 + indent, y, LIME if line["ok"] else RED)
            else:
                text(stripped, PAD + 16 + indent, y, CODE)

            y += LINE

    else:
        for line in part["lines"]:
            text(line, PAD + 4, y)
            y += LINE

        docs = docs_line(part["links"])

        if docs:
            for line in wrap(docs, WIDTH - 2 * PAD - 8):
                text(line, PAD + 4, y + 4, MUTED)
                y += LINE

    text("Select: next   Back: close" if not last else "Select or Back: close", PAD + 4, HEIGHT - 20, MUTED)


# The desk


def pick(title, options, selected, ticks):
    """The door rules at the desk: one option at a time, with the policy it would put on the door."""
    label, lines = options[selected]
    box(4, 4, WIDTH - 8, HEIGHT - 8, color.rgb(11, 9, 16, 245))
    text(title, PAD + 4, PAD + 2, SUN, TITLE)
    text("%d of %d: %s" % (selected + 1, len(options), label), PAD + 4, PAD + 24, LIME)
    code(lines, PAD + 4, PAD + 42)
    text("Left/Right: compare   Select: choose   Back: later", PAD + 4, HEIGHT - 20, MUTED)


# Full-screen pages: the title, the journal and the endings


def panel(title, pen=SUN):
    box(4, 4, WIDTH - 8, HEIGHT - 8, color.rgb(11, 9, 16, 245), pen)
    text(title, PAD + 4, PAD + 2, pen, TITLE)


def paragraph(words, y, pen=TEXT, x=PAD + 4, width=WIDTH - 2 * PAD - 8, limit=None):
    for line in wrap(words, width)[:limit]:
        text(line, x, y, pen)
        y += LINE

    return y


def tabs(names, selected):
    x = PAD + 4
    screen.font = BODY

    for index, name in enumerate(names):
        width = screen.measure_text(name)[0]

        if index == selected:
            screen.pen = SUN
            screen.rectangle(x - 3, 30, width + 6, 14)
            text(name, x, 31, NIGHT_DEEP)
        else:
            text(name, x, 31, MUTED)

        x += width + 12
