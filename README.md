# uc4-tool

A command-line tool for the setups of the
[Faderfox UC4](https://www.faderfox.de/uc4.html) MIDI controller: write a
setup as a text file, turn it into a sysex dump, and send it to the UC4.
It also reads the dumps the UC4 sends, for backups and for seeing what is in
a setup.

On the device, a setup is 264 controls to edit one by one. As a file it can
be written from the MIDI implementation chart of a synth in a few minutes.

- [docs/setup-file.md](docs/setup-file.md): the setup file format
- [docs/sysex-format.md](docs/sysex-format.md): the UC4's dump format, which
  Faderfox doesn't document. Worked out from a UC4 with firmware 2.03.
- [setups/](setups/): setups ready to use

## Install

Needs Python 3.8 or later and PyYAML.

```
pip install .
```

or run it from the repository with `python3 -m uc4tool`. Sending and
receiving use ALSA raw MIDI, so they need Linux. The other commands run
anywhere.

## Use

```
uc4 info dump.syx                          what a dump holds
uc4 decode dump.syx -o setup.yaml          a dump as a setup file
uc4 decode all.syx --slot 3                one setup of a dump of all setups
uc4 encode setup.yaml -o setup.syx         a setup file as a dump
uc4 send setup.yaml                        ...and straight to the UC4
uc4 send backup.syx                        a dump
uc4 send all.syx --slot 3                  one setup of a dump of all setups
uc4 receive -o backup.syx                  save what the UC4 sends
```

The UC4 stores a dump of one setup in **the setup that is selected on it**
(encoder 1 in setup mode), also when the dump was made from another setup.
So any backup of one setup can be put in any of the 18 setups.

### Back up first

Sending overwrites a setup, and there is no undo. Save everything before
trying things out:

```
uc4 receive -o all-setups.syx
```

then on the UC4: hold shift and press edit twice (setup mode), and hold
encoder 8 (`SndA`). It takes about half a minute.

### Sending

The UC4 only takes a dump in receive mode:

1. hold shift and press edit twice (setup mode)
2. select the setup to overwrite with encoder 1
3. press encoder 7 and **keep it down until the display shows `rC00`**. A
   short press only shows the function name, `rEc`, and the data is ignored.

`uc4 send` prints these steps and waits for enter. `--yes` skips the
question, for scripts and agents; the UC4 still has to be in receive mode.
When the setup is stored, the UC4 shows its number (`SE05`).

## Setups

| File | For |
|---|---|
| `setups/op1-field.yaml` | teenage engineering OP-1 field: sound, effects, mixer, tape transport, sound slots |

## Limits

- Tested with firmware 2.03 only.
- Sends one setup at a time. A dump of all setups can be read and taken
  apart, but sending one back wasn't tried.
- The global settings (MIDI routing, the selected setup) aren't part of a
  setup dump.

## Tests

```
python3 -m pytest tests
```

The dumps in `tests/data` were sent or accepted by a real UC4.
