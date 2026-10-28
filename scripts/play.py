#!/usr/bin/env python3
"""Plays the game on a connected badge with made-up button presses, then saves a screenshot.

Lets you check the game without pressing the badge's buttons. The game runs from /state/pqdev, a scratch
copy on the badge's writable storage, with its own save file, so it never touches the installed game.

    python3 scripts/play.py "select select wait:20 right*3 hold:up:30" --shot shot.png

Steps, separated by spaces:
    select, back, menu, up, down, left, right   press a button for one frame
    NAME*N                                      press it N times
    hold:NAME:FRAMES                            hold a direction for that many frames
    wait:FRAMES                                 let the game run
Each frame is 33 ms of game time. --setup runs Python on the badge first, with the game as `g`.
"""

import argparse
import os
import struct
import subprocess
import sys
import zlib

ROOT = os.path.join(os.path.dirname(__file__), "..")
APP = os.path.join(ROOT, "badge", "pomerium_quest")
DEV = "/state/pqdev"
FRAME_MS = 33


def mpremote(*args):
    port = os.environ.get("BADGE_PORT", "auto")
    result = subprocess.run(["mpremote", "connect", port, *args], capture_output=True, text=True)

    if result.returncode != 0:
        sys.exit(result.stdout + result.stderr)

    return result.stdout


def sync():
    """Copies the app to the badge's scratch folder."""
    files = [name for name in os.listdir(APP) if name.endswith(".py")]
    args = ["exec", "import os\nfor p in ('%s', '%s/assets'):\n    try: os.mkdir(p)\n    except OSError: pass" % (DEV, DEV)]

    for name in files:
        args += ["+", "cp", os.path.join(APP, name), ":%s/%s" % (DEV, name)]

    for name in os.listdir(os.path.join(APP, "assets")):
        args += ["+", "cp", os.path.join(APP, "assets", name), ":%s/assets/%s" % (DEV, name)]

    mpremote(*args)


def frames(steps):
    """Turns the steps into (pressed, held) for each frame."""
    out = []

    for step in steps.split():
        if step.startswith("wait:"):
            out += [((), ())] * int(step[5:])
        elif step.startswith("hold:"):
            _, name, count = step.split(":")
            out += [((name,), (name,))] + [((), (name,))] * (int(count) - 1)
        else:
            name, _, times = step.partition("*")

            for _ in range(int(times or 1)):
                out += [((name,), (name,)), ((), ()), ((), ()), ((), ())]

    return out


def program(steps, setup, shot):
    return "\n".join(
        [
            "import os, sys",
            "os.chdir('%s')" % DEV,
            "sys.path.insert(0, '%s')" % DEV,
            "badge.mode(HIRES)",
            "screen.antialias = image.X2",
            "import game",
            "game.SAVE_PATH = '%s/save.json'" % DEV,
            "g = game.Game()",
            "now = 1000",
            setup,
            "for pressed, held in %r:" % (frames(steps),),
            "    g.update(set(pressed), set(held), now)",
            "    now += %d" % FRAME_MS,
            "g.draw()",
            "print('stage', g.quest.stage, 'at', g.player.x, g.player.y, 'overlay', type(g.overlay).__name__ if g.overlay else None)",
            "open('%s/shot.raw', 'wb').write(screen.raw)" % DEV if shot else "",
        ]
    )


def png(raw, path, width=320, height=240):
    rows = []

    for y in range(height):
        row = bytearray([0])

        for x in range(width):
            (pixel,) = struct.unpack_from("<H", raw, (y * width + x) * 2)
            r, g, b = (pixel >> 11) & 31, (pixel >> 5) & 63, pixel & 31
            row += bytes((r * 255 // 31, g * 255 // 63, b * 255 // 31))

        rows.append(bytes(row))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    with open(path, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("steps", nargs="?", default="")
    parser.add_argument("--setup", default="")
    parser.add_argument("--shot")
    parser.add_argument("--fresh", action="store_true", help="delete the scratch save first")
    parser.add_argument("--no-sync", action="store_true")
    args = parser.parse_args()

    if not args.no_sync:
        sync()

    if args.fresh:
        mpremote("exec", "import os\ntry: os.remove('%s/save.json')\nexcept OSError: pass" % DEV)

    script = os.path.join(os.environ.get("TMPDIR", "/tmp"), "pq-play.py")

    with open(script, "w") as file:
        file.write(program(args.steps, args.setup, args.shot))

    print(mpremote("run", script).strip())

    if args.shot:
        raw = os.path.join(os.environ.get("TMPDIR", "/tmp"), "pq-shot.raw")
        mpremote("cp", ":%s/shot.raw" % DEV, raw)

        with open(raw, "rb") as file:
            png(file.read(), args.shot)

        print("screenshot:", args.shot)


if __name__ == "__main__":
    main()
