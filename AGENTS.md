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

## The badge

- MicroPython 1.29 on an RP2350, 320x240 in `HIRES` mode, about 8 MB of RAM and about 1 MB of free flash.
  Flash is the tight budget, so keep sprite sheets small.
- Apps live in `/system/apps/<name>/` with an `__init__.py` that calls `run(update)`. Save state under
  `/state/`.
- The badge firmware provides `badge`, `screen`, `image`, `color`, `font`, `shape`, `run` and the
  `BUTTON_*` constants as builtins, so apps don't import them.

## Setting up the badge

The game installs as one app folder, `/system/apps/pomerium_quest/`. The launcher menu lists every folder in
`/system/apps/` that has an `__init__.py` and titles it from the folder name, so `pomerium_quest` shows up
as "Pomerium Quest". There's nothing else to register.

1. **Install `mpremote`** if it's missing: `pipx install mpremote` (or `pip install --user mpremote`).
2. **Find the badge.** Plug it in over USB-C with a data cable. On macOS it appears as
   `/dev/cu.usbmodem*`; on Linux as `/dev/ttyACM*`. To confirm it's the badge, run
   `ioreg -p IOUSB -l -w0 | grep -i badger` (macOS) or `lsusb | grep -i pimoroni` (Linux). It reports as
   "GitHub Badger 2350 MicroPython" from Pimoroni. If no port appears, the badge may be asleep: press any
   button to wake it.
3. **Check it responds**:
   `mpremote connect <port> exec "import sys; print(sys.implementation)"`. Connecting interrupts whatever
   app is running, which is expected.
4. **Check there's room**: `mpremote connect <port> exec "import os; s=os.statvfs('/'); print(s[0]*s[3])"`
   prints the free bytes. The app must fit with some to spare.
5. **Copy the app** from the repo's `badge/pomerium_quest/` folder:
   `mpremote connect <port> mkdir :/system/apps/pomerium_quest` (ignore "file exists"), then
   `mpremote connect <port> cp -r badge/pomerium_quest/. :/system/apps/pomerium_quest/`.
   Use `mpremote`, not Finder: copying through the badge's USB disk mode leaves macOS `._*` files behind.
6. **Restart into the menu**: `mpremote connect <port> reset`. Pick "Pomerium Quest" with the d-pad and
   press Select.

To run the game straight away while developing, without going through the menu, use
`mpremote connect <port> exec "launch('/system/apps/pomerium_quest')"`. Errors print to the terminal.

Other things to know:

- **Saves** live in `/state/pomerium_quest.json`. Delete it with `mpremote connect <port> rm
  :/state/pomerium_quest.json` to start the quest over. Never touch other files in `/state/` or `/system/`
  outside the app's own folder: they belong to the badge's other apps and its launcher.
- **Removing the app**: `mpremote connect <port> rm -r :/system/apps/pomerium_quest`.
- **USB disk mode** (the Mass Storage app, or double-tapping reset) mounts the badge as a drive instead of a
  serial port. `mpremote` can't connect while it's in that mode; reset the badge to leave it.
- **`secrets.py`** on the badge holds the owner's Wi-Fi details. The game doesn't need Wi-Fi, so never read,
  print or copy it.

## Commits

- Commit often, one conventional commit with a scope per change that stands on its own.
- Don't rewrite history that's already pushed.
