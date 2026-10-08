# Setup files

A setup file describes one UC4 setup in YAML: what every control sends. The
tool turns it into a sysex dump for any of the 18 setup slots
(`uc4 encode`, `uc4 send`), and turns a dump into a setup file
(`uc4 decode`).

A setup has 8 encoder groups and 8 fader groups, selected separately on the
device:

- an **encoder group** has 8 encoders, their 8 push buttons, and a name of 4
  characters
- a **fader group** has 8 faders, fader 9, and 8 green buttons

```yaml
uc4: 1                # format of this file
name: my synth        # for you; not sent to the UC4
firmware: "2.03"      # firmware version written into the dump
channel: 1            # MIDI channel of every control that doesn't give one

defaults:             # for the controls listed below
  enc: {mode: acc2}

encoder_groups:
  - name: "FILt"
    enc: [74, 71, {cc: 10, display: bipolar}]
    push: [{note: 60}]

fader_groups:
  - fader: [7, 11]
    fader9: 1
    button: [{cc: 64, mode: toggle}]
```

## Controls

A control is written as

- a **number**: the controller number, everything else from the defaults
- a **mapping** of the fields below, for anything else
- `~` (or nothing, at the end of a list): the control isn't used

| Field | | |
|---|---|---|
| `type` | what is sent | see the tables below |
| `channel` | MIDI channel | 1-16 |
| `number` | controller or note number | 0-127; 0-31 for `cc14` |
| `min`, `max` | lower and upper value | 0-127. `min` above `max` turns a control around. Not used by the relative types. |
| `mode` | | see below |
| `display` | the display, or the LED of a green button (also written `led`) | see below |
| `label` | a note for you | ignored |

`cc: 74` is short for `type: cc, number: 74`; `note: 60` and `cc14: 1` work
the same way.

### Encoders

| `type` | Sends |
|---|---|
| `cc` | controller, 0-127 |
| `cc_rel1` | controller, relative: 1 = up, 127 = down |
| `cc_rel2` | controller, relative: 65 = up, 63 = down |
| `cc14` | 14 bit controller, on `number` and `number + 32` |
| `program` | program change |
| `pitchbend` | pitch bend |
| `aftertouch` | channel pressure |

`mode`: `acc0` (no acceleration when turned fast) to `acc3` (most).
`display`: `off`, `std` (0 to 127), `bipolar` (-63 to 63).

### Push buttons and green buttons

| `type` | Sends |
|---|---|
| `off` | nothing |
| `note` | note on with velocity `max`, note off with velocity `min` |
| `cc` | controller with the value `max`, then `min` |
| `program` | program change to `max`, then to `min`. Give both the same value for a button that selects one program. |
| `aftertouch` | channel pressure `max`, then `min` |

`mode`: `momentary` (`max` on press, `min` on release) or `toggle` (`max`
and `min` on alternate presses).
`led`, for green buttons: `off`, `std` (lit by the button, and by the same
message coming in), `ext` (lit by incoming messages only).

### Faders

`type`: `cc`, `program`, `pitchbend`, `aftertouch`.
`mode`: `jump` (sends as soon as it moves) or `snap` (sends once it has
passed the last value).
`display`: `off`, `std`, `bipolar`.

## Defaults

A control that is listed gets, for the fields it doesn't give:

| | type | mode | display | min, max |
|---|---|---|---|---|
| `enc` | `cc` | `acc3` | `std` | 0, 127 |
| `push` | `cc` | `momentary` | | 0, 127 |
| `button` | `cc` | `momentary` | `std` | 0, 127 |
| `fader` | `cc` | `jump` | `std` | 0, 127 |

and the file's `channel`. `defaults:` changes these for a kind of control.

A control that isn't listed is **unused**. Unused buttons send nothing
(`type: off`). Encoders and faders can't be switched off, so unused ones send
controller 119 on channel 16, which no MIDI device should react to, and show
nothing on the display. `unused:` changes this for a kind of control, in the
same way as `defaults:`.

An encoder group without a `name` is called `GrP1` to `GrP8`.

## Names

The display has these characters:

```
0 1 2 3 4 5 6 7 8 9
A b C d E F G H I J L M n O P q r S t U X y Z
- _ ' " =  and the blank
```

There is no K, V or W. Upper and lower case are the same to the tool. `M`
looks like an upside-down U, `X` like an H, `Z` like a 2. Put names in quotes.

## YAML notes

- Repeat things with anchors: `fader: &faders [...]` and later
  `fader: *faders`. See `setups/op1-field.yaml`, where the faders are the same
  in every fader group.
- YAML reads a bare `off` as "false". The tool takes that as `off`, so both
  `type: off` and `type: "off"` work.
- Where a code has no name (see `docs/sysex-format.md`), its number can be
  written: `mode: 2`. `uc4 decode` writes numbers for codes it doesn't know,
  so that a decoded file always encodes back to the same dump.
