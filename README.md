# Pomerium Quest: Badge Edition

A pocket-sized port of [Pomerium Quest](https://github.com/nickytonline/pomerium-quest) for the GitHub
Universe badge (Pimoroni Badger 2350, MicroPython). You play the Pomerium Pomeranian, every gate in the
kingdom has a Pomerium policy, and when a guard turns you away the game shows you the exact rule that failed.

## How this differs from the browser game

The browser game runs a real Pomerium in Kubernetes with Keycloak as the identity provider, so every gate is
a real route and Pomerium makes every decision. A badge can't run any of that, so this edition **simulates**
it:

| Browser game                                   | Badge                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------- |
| Keycloak signs you in                          | The Oracle signs you in on the badge                                      |
| The Oracle adds you to groups in Keycloak      | The Oracle adds you to groups in your saved identity on the badge         |
| Pomerium evaluates each gate's policy          | A port of the game's policy evaluator checks the same policy on the badge |
| Policies live in `zones.ts`                    | Generated from the same `zones.ts`, so they can't drift                   |

The policies, claims and rules the game teaches are the same ones the browser game uses, and they're true of
open-source Pomerium. Only who evaluates them changes.

What else is different on the badge:

- **Your house's door rules are chosen, not typed.** Each letter on your desk offers three door policies,
  shown as the YAML Pomerium would read. Pick one, and the letter's visitors try the door against it.
- **Docs links are QR codes.** Open the journal's Lessons tab, pick a lesson and press Select to scan its
  Pomerium docs page with your phone.
- **The badge has no speaker**, so the game is silent.

## Controls

The game is played with the badge's own buttons, mapped to match the browser game:

| Action                                         | On the badge             | In the browser game                       |
| ---------------------------------------------- | ------------------------ | ----------------------------------------- |
| Move                                           | Up, Down, Left and Right | The arrow keys, or the W, A, S and D keys |
| Talk, read a sign, open a chest or knock       | Select                   | E or Enter                                |
| Go on to the next page of a sign or a talk     | Select or Back           | E or Enter                                |
| Swing your sword                               | Back                     | Space or J                                |
| Close a denial screen or the journal           | Back                     | Esc                                       |
| Pick an answer, or compare door rules          | Up and Down, Left and Right, then Select | Click                  |
| Open the journal (your quest, your claims, lessons, the access log, start over) | Menu | I                     |
| Leave the game for the badge's app list        | Home                     | Not in the browser game                   |

The game saves as you play, so you can leave with Home and carry on later.

## Installing on your badge

You need macOS or Linux, Python 3 and [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html)
(`pipx install mpremote`). Plug the badge in over USB-C, then run:

```sh
./scripts/install.sh
```

The badge only lets a computer write apps while it's in USB disk mode, so the script switches it into that
mode, copies the game, puts Pomerium Quest second in the badge's app list, and ejects the drive. Press the
badge's reset button if it doesn't restart on its own, then pick Pomerium Quest. [AGENTS.md](AGENTS.md) has
the details, including how to start the quest over.

## How it fits together

| Path                          | What it is                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| `badge/pomerium_quest/`       | The app the badge runs                                                             |
| `.../data.py` and `assets/`   | Generated from Pomerium Quest: zones, signs, books, letters, the map, sprite sheets |
| `.../ppl.py`                  | The policy evaluator, standing in for Pomerium                                     |
| `.../quest.py`                | Quest stages and saving, with the badge playing the identity provider               |
| `.../story.py`, `house.py`    | What everyone says, and what happens at each gate and at your door                  |
| `.../household.py`            | Life around your house: the traveler, the bread, the guard who shows visitors out   |
| `.../game.py`, `ui.py`        | The overworld and everything drawn over it                                          |
| `scripts/generate.mjs`        | Regenerates the data from a Pomerium Quest checkout next to this one               |
| `scripts/play.py`             | Plays the game on a connected badge with scripted presses and takes a screenshot   |
| `tests/`                      | Unit tests, plus a full playthrough that runs on the badge                         |

```sh
node scripts/generate.mjs                  # after the browser game's zones, map or words change
python3 -m unittest discover -s tests      # unit tests, on this computer
python3 scripts/play.py --fresh --setup "$(cat tests/badge_playthrough.py)"   # the whole quest, on the badge
```

The generator also saves the browser game's own policy decisions as test fixtures, and the tests check the
badge's evaluator makes every one of them the same way.

## License

[Apache License 2.0](LICENSE), the same as Pomerium Quest.
