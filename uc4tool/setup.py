"""One UC4 setup, and where it sits in the UC4's setup memory."""

from dataclasses import dataclass, field

from . import sysex

SETUPS = 18
GROUPS = 8
CONTROLS = 8
NAME_LENGTH = 4
KINDS = ("enc", "push", "button", "fader")

# setup memory, see docs/sysex-format.md
ADDR_NAMES = 0x1480
ADDR_FADER9 = 0x1700
ADDR_ROWS = 0x1C00
NAMES_SIZE = GROUPS * NAME_LENGTH      # per setup
FADER9_SIZE = 0x40                     # per setup, 40 bytes used
SETUP_SIZE = 0x500                     # per setup: 20 rows of 64 bytes
ROW_SIZE = GROUPS * CONTROLS
FADER9_ENTRY = 5
PAD = 0xFF


@dataclass
class Control:
    """What one control sends. type, mode and display are the raw codes."""
    type: int = 0
    channel: int = 1    # 1-16
    number: int = 0
    low: int = 0
    high: int = 127
    mode: int = 0
    display: int = 0

    def to_bytes(self):
        return ((self.type << 4) | (self.channel - 1), self.number, self.low,
                self.high, (self.mode << 4) | self.display)

    @classmethod
    def from_bytes(cls, b):
        return cls(type=b[0] >> 4, channel=(b[0] & 15) + 1, number=b[1],
                   low=b[2], high=b[3], mode=b[4] >> 4, display=b[4] & 15)


@dataclass
class Setup:
    names: list = field(default_factory=list)     # 8 lists of 4 character codes
    controls: dict = field(default_factory=dict)  # kind -> 64 Controls, by group
    fader9: list = field(default_factory=list)    # 8 Controls, one per group
    firmware: tuple = (2, 3)

    def control(self, kind, group, n):
        """The control n (1-8) of a group (1-8)."""
        return self.controls[kind][(group - 1) * CONTROLS + n - 1]


def slot_addresses(slot):
    return (ADDR_NAMES + (slot - 1) * NAMES_SIZE,
            ADDR_FADER9 + (slot - 1) * FADER9_SIZE,
            ADDR_ROWS + (slot - 1) * SETUP_SIZE)


def slots_in(dump):
    """The setup numbers a dump holds."""
    mem = dump.memory()
    return [s for s in range(1, SETUPS + 1) if slot_addresses(s)[2] in mem]


def from_dump(dump, slot=None):
    """Read a setup from a dump. slot is needed when the dump holds several."""
    slots = slots_in(dump)
    if slot is None:
        if len(slots) != 1:
            raise ValueError("the dump holds setups %s: choose one"
                             % ", ".join(map(str, slots)))
        slot = slots[0]
    elif slot not in slots:
        raise ValueError("the dump doesn't hold setup %d" % slot)
    mem = dump.memory()
    a_names, a_fader9, a_rows = slot_addresses(slot)

    def read(addr, n):
        try:
            return [mem[addr + i] for i in range(n)]
        except KeyError:
            raise ValueError("the dump lacks memory at 0x%04X" % addr)

    setup = Setup(firmware=tuple(dump.firmware))
    flat = read(a_names, NAMES_SIZE)
    setup.names = [flat[g * NAME_LENGTH:(g + 1) * NAME_LENGTH]
                   for g in range(GROUPS)]
    f9 = read(a_fader9, GROUPS * FADER9_ENTRY)
    setup.fader9 = [Control.from_bytes(f9[g * 5:g * 5 + 5]) for g in range(GROUPS)]
    for k, kind in enumerate(KINDS):
        rows = [read(a_rows + (k * 5 + r) * ROW_SIZE, ROW_SIZE) for r in range(5)]
        setup.controls[kind] = [
            Control.from_bytes([rows[r][i] for r in range(5)])
            for i in range(ROW_SIZE)]
    return setup, slot


def to_dump(setup, slot):
    """A one-setup dump that puts the setup in a slot."""
    if not 1 <= slot <= SETUPS:
        raise ValueError("there are setups 1 to %d" % SETUPS)
    a_names, a_fader9, a_rows = slot_addresses(slot)
    dump = sysex.Dump(dump_type=sysex.DUMP_ONE_SETUP, firmware=tuple(setup.firmware))
    dump.blocks.append((a_names, bytes(c for name in setup.names for c in name)))
    f9 = [b for control in setup.fader9 for b in control.to_bytes()]
    f9 += [PAD] * (FADER9_SIZE - len(f9))
    dump.blocks.append((a_fader9, bytes(f9)))
    for k, kind in enumerate(KINDS):
        fields = [control.to_bytes() for control in setup.controls[kind]]
        for r in range(5):
            dump.blocks.append((a_rows + (k * 5 + r) * ROW_SIZE,
                                bytes(f[r] for f in fields)))
    return dump
