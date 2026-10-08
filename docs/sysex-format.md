# The setup dump format of the Faderfox UC4

Faderfox doesn't publish the format of the UC4's sysex dumps. This is what
was worked out from a UC4 with **firmware 2.03**: by reading dumps the device
sent, by comparing them with the factory settings listed in the manual, and by
sending setups to the device and recording what its controls then sent.

Everything below is confirmed on the device unless it says otherwise. What is
still unknown is listed at the end.

Numbers with `0x` are hexadecimal. Groups, controls, setups and MIDI channels
are counted from 1, as on the device.

## The dump

A dump is a single sysex message. The UC4 sends two kinds:

| Made with | Holds | Size |
|---|---|---|
| setup mode, hold encoder 4 (`Sndc`) | the selected setup | 5072 bytes |
| setup mode, hold encoder 8 (`SndA`) | all 18 setups | 100640 bytes |

The message has no manufacturer id. After the start byte `F0` come three zero
bytes, then a sequence of three-byte tokens, then `F7`.

### Tokens

Every byte of content is sent as a token of three bytes, which keeps all of
them below `0x80`:

```
tag   0x20 + high nibble   0x10 + low nibble
```

For example `4D 21 14` is tag `0x4D` with the value `0x14`.

| Tag | | Value |
|---|---|---|
| `0x41` `A` | device | `0x06` |
| `0x42` `B` | dump type | `0x02` one setup, `0x03` all setups |
| `0x43` `C` | firmware version, major | `0x02` |
| `0x44` `D` | firmware version, minor | `0x03` |
| `0x49` `I` | block address, high byte | |
| `0x4A` `J` | block address, low byte | |
| `0x4D` `M` | one byte of block data | |
| `0x4B` `K` | block checksum, high byte | |
| `0x4C` `L` | block checksum, low byte | |
| `0x4F` `O` | end of the dump | `0x06` |

### Layout

```
F0 00 00 00
A B C D                          header
I J  M M M ... M  K L  00 x 30   block, repeated
O
F7
```

- A block is an address, its data bytes, and a checksum. The **checksum** is
  the sum of the block's data bytes, as a 16 bit number.
- After every block come **30 zero bytes**. They carry nothing; at the speed
  of a MIDI cable they take about 10 ms, which is presumably the time the UC4
  needs to store the block.
- Blocks hold 64 bytes of data, except the group names in a one-setup dump
  (32 bytes).

## Setup memory

The addresses in the blocks are addresses in the UC4's setup memory. A dump
of all setups is that memory from `0x1480` to `0x7FFF` in 430 blocks of 64
bytes. A dump of one setup holds only the 22 blocks of that setup, at the
addresses of the setup it was made from.

The UC4 doesn't go by these addresses when it takes a dump of one setup: it
stores the dump in **the setup that is selected on it** (encoder 1 in setup
mode). A dump with the addresses of setup 5, sent while setup 4 was selected,
was stored in setup 4.

`s` is the setup number, 1 to 18.

| Address | Size | |
|---|---|---|
| `0x1480 + (s-1) * 0x20` | 32 | names of the 8 encoder groups, 4 characters each |
| `0x16C0` | 64 | unknown. `0x16E0`-`0x16E3` held a group name, the rest `0xFF`. Probably the copy memory for a group name (setup mode, `CPYn`). |
| `0x1700 + (s-1) * 0x40` | 64 | fader 9: 8 groups x 5 bytes, then 24 bytes `0xFF` |
| `0x1B80` | 128 | `0xFF` |
| `0x1C00 + (s-1) * 0x500` | 1280 | the controls: 20 rows of 64 bytes |
| `0x7600` | 2560 | the size of two more setups. Mostly `0xFF`; from `0x7B00` on, each row of the setup layout held values for 8 controls only. Probably the copy memory for a setup or a group. |

### The controls

A setup has 20 rows of 64 bytes. A row holds one property of one kind of
control, for 8 groups x 8 controls: the byte for control `n` of group `g` is
at `(g-1) * 8 + (n-1)`.

There are five rows for each kind, in this order:

| Rows | Kind |
|---|---|
| 0-4 | encoders |
| 5-9 | encoder push buttons |
| 10-14 | green buttons |
| 15-19 | faders 1-8 |

and within a kind:

| Row | Property | |
|---|---|---|
| 0 | type and channel | type in the high nibble, channel - 1 in the low |
| 1 | number | controller or note number, 0-127 |
| 2 | lower value | 0-127 |
| 3 | upper value | 0-127 |
| 4 | mode and display | mode in the high nibble, display in the low |

Encoder groups and fader/button groups are selected separately on the device,
but are stored the same way: group `g` of the encoder rows is encoder group
`g`, group `g` of the fader and button rows is fader/button group `g`.

**Fader 9** has the same five properties, as five bytes in a row (type and
channel, number, lower, upper, mode and display), once for each of the 8
fader groups.

### Type

| Code | Encoder | Sends |
|---|---|---|
| 0 | `CCr1` | controller, relative: 1 for a step up, 127 for a step down |
| 1 | `CCr2` | controller, relative: 65 for a step up, 63 for a step down |
| 2 | `CCAb` | controller, 0-127 |
| 3 | `PrGC` | program change |
| 4 | `CCAh` | 14 bit controller: the high 7 bits on `number`, the low 7 bits on `number + 32` |
| 5 | `Pbnd` | pitch bend, in steps of 1 of 16384 |
| 6 | `AFtt` | channel pressure |

| Code | Push button, green button | Sends |
|---|---|---|
| 0 | `OFF` | nothing |
| 1 | `notE` | note on with the upper value as velocity; note off (`0x80`) with the lower value as velocity |
| 2 | `CC` | controller with the upper value, then with the lower value |
| 3 | `PrGC` | program change to the upper value, then to the lower value |
| 4 | `AFtt` | channel pressure with the upper value, then with the lower value |

| Code | Fader | Sends |
|---|---|---|
| 0 | `CCAb` | controller, 0-127 |
| 1 | `PrGC` | program change |
| 2 | `Pbnd` | pitch bend, 7 bit: in steps of 129 of 16384 |
| 3 | `AFtt` | channel pressure |

### Mode

| Code | Encoder | Push button, green button | Fader |
|---|---|---|---|
| 0 | `Acc0` no acceleration | `btn` momentary: upper value on press, lower on release | `JMP` jump |
| 1 | `Acc1` | `toGL` toggle: upper and lower value on alternate presses | `SnAP` snap |
| 2 | `Acc2` | | |
| 3 | `Acc3` most acceleration | | |

On the device, code 3 was seen to accelerate and code 0 not to. Codes 1 and 2
weren't told apart; their order is that of the device's menu. Jump is what the
factory setups 1-16 have and snap what setups 17 and 18 have, both as the
manual says.

### Display

| Code | Encoder, fader | Green button |
|---|---|---|
| 0 | `OFF` nothing shown | `OFF` LED never lit |
| 1 | `Std` 0 to 127 | `Std` LED lit by the button and by incoming messages |
| 2 | `bPoL` -63 to 63 | `EXt` LED lit by incoming messages only |

The display nibble of an **encoder push button** has no setting on the device.
It is 0 in the factory setups; 2 was seen on push buttons edited on the
device.

### Characters

A group name is four codes for the 4 digit display:

| Codes | Characters |
|---|---|
| `0x00`-`0x09` | `0 1 2 3 4 5 6 7 8 9` |
| `0x0A`-`0x13` | `A b C d E F G H I J` |
| `0x14`-`0x1A` | `L M n O P q r` |
| `0x1B`-`0x20` | `S t U X y Z` |
| `0x21`-`0x25` | `-` `_` `'` `"` `=` |
| `0x26` | blank |

There is no K, V or W. On the seven segments `M` is drawn like an upside-down
U, `X` like an H, and `Z` like a 2. Codes above `0x26` weren't tried.

## Sending a dump to the UC4

The UC4 takes a dump only in receive mode: in setup mode (hold shift, press
edit twice), press encoder 7 and **keep it down** while a dash runs across the
display, until the display shows `rC00`. A short press only shows the function
name, `rEc`, and incoming data is ignored. The dot at the bottom right of the
display flashes for incoming MIDI in either case, so it tells nothing.

When a one-setup dump has been stored the display shows the number of the
setup it was stored in, the selected one (`SE15`). A dump that isn't taken
leaves the display as it was.

Sent over USB in chunks of 16 bytes every 10 ms (1600 bytes a second, half
the speed of a MIDI cable), dumps were stored every time the display showed
`rC00`. Faster wasn't tried with the device known to be in receive mode.

## Not known

- Anything about other firmware versions. The header carries the version; the
  tool writes 2.03.
- Whether the UC4 checks the header's version or the checksums, and what it
  does with a wrong one (`Err`, presumably).
- The regions at `0x16C0` and `0x7600` (see above), and where the routing
  mode and the number of the selected setup are kept. They aren't in a dump
  of one setup.
- Whether a dump of all setups can be sent back in the same way. Only
  one-setup dumps were sent.
- What the `00` of `rC00` stands for, and whether it changes.
- The acceleration codes 1 and 2, the display nibble of push buttons and
  character codes above `0x26`, as noted above.
