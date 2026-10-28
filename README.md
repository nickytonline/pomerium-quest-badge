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

## License

[Apache License 2.0](LICENSE), the same as Pomerium Quest.
