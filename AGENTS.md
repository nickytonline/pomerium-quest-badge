# Agent guidelines

Pomerium Quest: Badge Edition is a MicroPython port of
[Pomerium Quest](https://github.com/nickytonline/pomerium-quest) for the Pimoroni Badger 2350 (the GitHub
Universe badge). The [README](README.md) explains how it differs from the browser game.

## Simulation

- The repo (README, docs, comments) says plainly that Pomerium and the identity provider are simulated.
- The game itself doesn't: it's a teaching tool, so in-game text talks about policies and claims as
  Pomerium would apply them.
- Everything the game teaches must still be true of open-source Pomerium, for example `claim/groups`,
  not `groups`.
- Policies, map and dialogue come from the browser game's source, generated rather than hand-copied, so
  signs and denial screens never drift from `zones.ts`.

## Working on the game

- The README's "How it fits together" table maps the code. `data.py` and `assets/` are generated: change
  the browser game and run `node scripts/generate.mjs` (it expects a Pomerium Quest checkout at
  `../pomerium-quest`, or set `QUEST_DIR`). Never edit them by hand.
- `data.py`, `ppl.py`, `quest.py`, `story.py` and `house.py` must run on desktop Python too, so they never
  touch the badge's builtins: the unit tests import them. Only `game.py`, `ui.py` and `__init__.py` draw.
- Dialogue in `story.py` and `house.py` is ported by hand from the browser game's `story.ts` and
  `house-story.ts`. Keep it in step with them.
- `python3 -m unittest discover -s tests` must pass before every commit.
- Check anything on screen with `scripts/play.py`: it plays the game on the connected badge from a scratch
  copy in `/state/pqdev` (its own save, so the installed game is untouched) and saves a screenshot.
  `--setup` runs Python first, with the game as `g`, to jump to any stage. Read the screenshot rather than
  guessing at layout. `tests/badge_playthrough.py` plays the whole quest this way; run it after changing
  `game.py`.
- MicroPython has no `dataclasses`, `typing` or `re.finditer`. Keep to plain classes, dicts and tuples.
- Frames take about 32 ms. The map is drawn once into one big image, and each frame blits a window of it,
  so redraw a tile with `set_tile` when it changes rather than redrawing the map.

## The badge

- MicroPython 1.29 on an RP2350, 320x240 in `HIRES` mode and about 8 MB of RAM.
- The badge has two filesystems:
  - `/system` is a 12 MB FAT drive holding the launcher and every app, with about 9 MB free. MicroPython
    mounts it **read-only**, so only a computer can write it, while the badge is in USB disk mode. On the
    drive, `apps/` is `/system/apps/`.
  - `/` is a small, writable littlefs (about 1 MB free) that holds `/state/`. Apps save there.
- Apps live in `/system/apps/<name>/` with an `__init__.py` that calls `run(update)`. This game saves to
  `/state/pomerium_quest.json`.
- The firmware provides `badge`, `screen`, `image`, `color`, `font`, `shape`, `run` and the `BUTTON_*`
  constants as builtins, so apps don't import them.
- The physical buttons are `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_LEFT`, `BUTTON_RIGHT`, `BUTTON_SELECT`,
  `BUTTON_BACK`, `BUTTON_MENU` and `BUTTON_HOME`. Home leaves the app for the launcher, so the game never
  uses it. The README's controls table is the mapping: change it, the in-game hints and the code together.

## Setting up the badge

`./scripts/install.sh` does the whole install. Run it, and only fall back to the manual steps below if it
fails. It needs macOS or Linux, Python 3 and `mpremote` (`pipx install mpremote`).

The launcher lists every folder in `/system/apps/` that has an `__init__.py`, titled from the folder name
(`pomerium_quest` shows as "Pomerium Quest"), and orders them by the `APP_ORDER` tuple in
`/system/apps/menu/app.py`. Pomerium Quest goes **second** in that tuple, after whatever is first (today
that's the owner's `zero_trust` app). That edit to the launcher is the only change made outside the game's
own folder.

What the script does, step by step:

1. **Find the badge.** Plugged in over USB-C, it shows up as a serial port: `/dev/cu.usbmodem*` on macOS,
   `/dev/ttyACM*` on Linux. To confirm it's the badge, run `ioreg -p IOUSB -l -w0 | grep -i badger` (macOS)
   or `lsusb | grep -i pimoroni` (Linux): it reports as "GitHub Badger 2350 MicroPython" from Pimoroni. If
   no port appears, press a button to wake it.
2. **Switch to USB disk mode**:
   `mpremote connect <port> exec "import powman; powman.reset_into_msc()"`. This is what the badge's Mass
   Storage app does. The badge reboots and mounts as a drive named `BADGER` (`/Volumes/BADGER` on macOS).
   Set `BADGE_DRIVE` if it mounts elsewhere. Never `import _msc` to get there: it switches modes
   mid-command and leaves `mpremote` hanging.
3. **Copy the app**: `cp -RX badge/pomerium_quest <drive>/apps/`. The `-X` matters on macOS: without it,
   copies leave `._*` files on the FAT drive, which then show up on the badge.
4. **Back up the launcher once**: copy `<drive>/apps/menu/app.py` to `.badge-backup/menu-app.py` in this
   repo (git ignores it). To undo the menu change, copy that file back onto the drive.
5. **Put the game second**: insert `    "pomerium_quest",` as the second line inside `APP_ORDER = (`,
   removing any copy already there, so running the install twice is safe.
6. **Eject**: delete any `._*` files under `<drive>/apps/pomerium_quest`, `sync`, then `diskutil eject <drive>` (macOS) or
   `umount <drive>` (Linux). The badge restarts into the launcher; if it doesn't, ask the owner to press
   its reset button.
7. **Check it**: once the serial port is back,
   `mpremote connect <port> exec "import os; print(os.listdir('/system/apps/pomerium_quest'))"` should
   list the app's files.

Other things to know:

- **Running it without the menu**, while developing:
  `mpremote connect <port> exec "launch('/system/apps/pomerium_quest')"`. Errors print to the terminal.
- **Starting the quest over**: `mpremote connect <port> rm :/state/pomerium_quest.json`. That works over
  serial because `/state` is writable.
- **Removing the game**: in disk mode, delete `<drive>/apps/pomerium_quest` and remove its line from
  `APP_ORDER` (or copy the backup back).
- **A firmware update** may replace the launcher and drop the game from `APP_ORDER`. Run the install again.
- Leave every other file in `/system` and `/state` alone: they belong to the launcher and the badge's other
  apps. **`secrets.py`** holds the owner's Wi-Fi details, and the game doesn't need Wi-Fi, so never read,
  print or copy it.
- You can't press the badge's buttons, so ask the owner to check anything played or visual.

## Commits

- Commit often, one conventional commit with a scope per change that stands on its own.
- Don't rewrite history that's already pushed.
