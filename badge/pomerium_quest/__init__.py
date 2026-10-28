APP_DIR = "/system/apps/pomerium_quest"

import os
import sys
import math

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)

# Colours sampled from the Pomerium sunset logo, matching the zero_trust app.
BG = color.rgb(14, 10, 32)
WHITE = color.rgb(255, 255, 255)
DIM = color.rgb(170, 160, 210)
LIME = color.rgb(200, 255, 40)
PINK = color.rgb(255, 60, 170)

TITLE = ("Pomerium", "Quest")
BOB_MS = 600


def centred(text, y):
    width, _ = screen.measure_text(text)
    screen.text(text, screen.width / 2 - width / 2, y)


def update():
    screen.pen = BG
    screen.clear()

    screen.font = font.smart
    screen.pen = WHITE
    y = 60

    for line in TITLE:
        centred(line, y)
        y += screen.measure_text(line)[1] + 4

    screen.pen = PINK
    screen.rectangle(screen.width / 2 - 30, y + 4, 60, 3)

    screen.font = font.ark
    screen.pen = DIM
    centred("The kingdom is still being built.", y + 24)

    # A gentle bob draws the eye to the prompt.
    bob = math.sin(badge.ticks / BOB_MS) * 2
    screen.pen = LIME
    centred("Home: back to the badge menu", screen.height - 30 + bob)


run(update)
