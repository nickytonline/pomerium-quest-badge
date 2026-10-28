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

## Controls

The game is played with the badge's own buttons, mapped to match the browser game:

| Action                                      | On the badge                    | In the browser game                       |
| ------------------------------------------- | ------------------------------- | ----------------------------------------- |
| Move                                        | Up, Down, Left and Right        | The arrow keys, or the W, A, S and D keys |
| Talk, read a sign, open a chest or a gate   | Select                          | E or Enter                                |
| Show the next line of what someone says     | Select                          | E or Enter                                |
| Swing your sword                            | Back                            | Space or J                                |
| Close a sign, a conversation or a denial    | Back                            | Esc                                       |
| Open the menu (journal, save, sound)        | Menu                            | Esc, or I for the journal                 |
| Leave the game for the badge's app list     | Home                            | Not in the browser game                   |

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

## License

[Apache License 2.0](LICENSE), the same as Pomerium Quest.
