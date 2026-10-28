import os
import sys

APP_DIR = __file__.rsplit("/", 1)[0] if "/" in __file__ else "/system/apps/pomerium_quest"

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

from game import BUTTONS, Game  # noqa: E402

game = Game()


def update():
    pressed = {name for name, button in BUTTONS.items() if badge.pressed(button)}

    if "home" in pressed:
        game.save(True)
        reset()

    held = {name for name, button in BUTTONS.items() if badge.held(button)}
    game.update(pressed, held, badge.ticks)
    game.draw()


run(update)
