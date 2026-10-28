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
- Talk to it with `mpremote connect /dev/cu.usbmodem*`. Copy files with `mpremote cp`, not Finder, which
  leaves `._*` files behind.

## Commits

- Commit often, one conventional commit with a scope per change that stands on its own.
- Don't rewrite history that's already pushed.
