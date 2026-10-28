#!/usr/bin/env bash
# Installs the game on a connected badge and makes it the second app in the menu.
#
# MicroPython mounts the badge's /system drive read-only, so apps can only be installed from a computer
# while the badge is in USB disk mode. This script switches the badge into that mode if it isn't already,
# copies the app, then ejects the drive.
#
# BADGE_DRIVE overrides where the drive is mounted (default /Volumes/BADGER on macOS).
# BADGE_PORT overrides the serial port mpremote uses (default: mpremote finds it).
set -euo pipefail

cd "$(dirname "$0")/.."

drive="${BADGE_DRIVE:-/Volumes/BADGER}"
port="${BADGE_PORT:-auto}"
backup=.badge-backup/menu-app.py

if [ ! -d "$drive/apps" ]; then
  echo "Switching the badge to USB disk mode"
  # The same call the badge's Mass Storage app makes: reboot straight into disk mode.
  mpremote connect "$port" exec "import powman; powman.reset_into_msc()" >/dev/null 2>&1 || true

  for _ in $(seq 30); do
    [ -d "$drive/apps" ] && break
    sleep 1
  done

  if [ ! -d "$drive/apps" ]; then
    echo "The badge's drive didn't appear at $drive. Open the Mass Storage app on the badge, then run this again." >&2
    exit 1
  fi
fi

echo "Copying the app to $drive/apps/pomerium_quest"
rm -rf "$drive/apps/pomerium_quest"
# Only the game's code and sprite sheets: not Python's caches from running the tests here. -X leaves out
# extended attributes, which macOS would otherwise write as ._* files on the FAT drive.
mkdir -p "$drive/apps/pomerium_quest/assets"
cp -X badge/pomerium_quest/*.py "$drive/apps/pomerium_quest/"
cp -X badge/pomerium_quest/assets/*.png "$drive/apps/pomerium_quest/assets/"

# The launcher orders apps by its APP_ORDER list. Keep the untouched original on this computer.
if [ ! -f "$backup" ]; then
  mkdir -p .badge-backup
  cp -X "$drive/apps/menu/app.py" "$backup"
  echo "Backed up the badge's menu to $backup"
fi

echo "Placing Pomerium Quest second in the menu"
python3 - "$drive/apps/menu/app.py" <<'PY'
import sys

path = sys.argv[1]
src = open(path).read()
lines = src.split('\n')
start = lines.index('APP_ORDER = (')
end = lines.index(')', start)
order = [line for line in lines[start + 1:end] if line.strip() != '"pomerium_quest",']
order.insert(1, '    "pomerium_quest",')
updated = '\n'.join(lines[:start + 1] + order + lines[end:])

if updated != src:
    open(path, 'w').write(updated)

print('Menu order starts:', ', '.join(line.strip(' ",') for line in order[:3]))
PY

# Clear any ._* files macOS left in and beside the game's folder, then make sure everything is written before
# ejecting.
find "$drive/apps/pomerium_quest" -name '._*' -delete
rm -f "$drive/apps/._pomerium_quest"
sync

if command -v diskutil >/dev/null; then
  diskutil eject "$drive" >/dev/null
else
  umount "$drive"
fi

echo "Installed. Press the badge's reset button if it doesn't restart on its own, then pick Pomerium Quest."
