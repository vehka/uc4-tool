"""The container format of a UC4 setup dump.

A dump is one sysex message: a header, blocks of the UC4's setup memory
and an end tag. Every byte is sent as three: a tag, then its high nibble
as 0x20 + n and its low nibble as 0x10 + n. See docs/sysex-format.md.
"""

from dataclasses import dataclass, field

TAG_DEVICE = 0x41
TAG_DUMP_TYPE = 0x42
TAG_VERSION_MAJOR = 0x43
TAG_VERSION_MINOR = 0x44
TAG_ADDR_HIGH = 0x49
TAG_ADDR_LOW = 0x4A
TAG_CHECKSUM_HIGH = 0x4B
TAG_CHECKSUM_LOW = 0x4C
TAG_DATA = 0x4D
TAG_END = 0x4F

DEVICE_UC4 = 0x06
DUMP_ONE_SETUP = 0x02
DUMP_ALL_SETUPS = 0x03

LEAD_ZEROS = 3   # after the sysex start byte
BLOCK_GAP = 30   # zero bytes after each block


class SysexError(ValueError):
    pass


@dataclass
class Dump:
    dump_type: int
    firmware: tuple = (2, 3)
    device: int = DEVICE_UC4
    blocks: list = field(default_factory=list)  # (address, bytes) in order

    def memory(self):
        """The dumped memory as {address: byte}."""
        mem = {}
        for addr, data in self.blocks:
            for i, value in enumerate(data):
                mem[addr + i] = value
        return mem


def parse(raw):
    """Parse the bytes of a dump. Checks the block checksums."""
    if len(raw) < 2 or raw[0] != 0xF0 or raw[-1] != 0xF7:
        raise SysexError("not a sysex message (no F0 ... F7)")
    tokens = []
    i = 1
    end = len(raw) - 1
    while i < end:
        tag = raw[i]
        if tag == 0:
            i += 1
            continue
        if i + 2 >= end + 1 or raw[i + 1] >> 4 != 2 or raw[i + 2] >> 4 != 1:
            raise SysexError("not a UC4 dump (bad byte at offset %d)" % i)
        tokens.append((tag, ((raw[i + 1] & 15) << 4) | (raw[i + 2] & 15)))
        i += 3

    head = dict(tokens[:4])
    if [t for t, _ in tokens[:4]] != [TAG_DEVICE, TAG_DUMP_TYPE,
                                      TAG_VERSION_MAJOR, TAG_VERSION_MINOR]:
        raise SysexError("not a UC4 dump (no header)")
    if not tokens or tokens[-1][0] != TAG_END:
        raise SysexError("the dump is cut short (no end tag)")
    dump = Dump(dump_type=head[TAG_DUMP_TYPE], device=head[TAG_DEVICE],
                firmware=(head[TAG_VERSION_MAJOR], head[TAG_VERSION_MINOR]))

    addr, data, checksum = None, bytearray(), 0
    for tag, value in tokens[4:-1]:
        if tag == TAG_ADDR_HIGH:
            addr, data = value << 8, bytearray()
        elif tag == TAG_ADDR_LOW:
            addr |= value
        elif tag == TAG_DATA:
            data.append(value)
        elif tag == TAG_CHECKSUM_HIGH:
            checksum = value << 8
        elif tag == TAG_CHECKSUM_LOW:
            checksum |= value
            if addr is None:
                raise SysexError("a block has no address")
            if sum(data) != checksum:
                raise SysexError("wrong checksum in the block at 0x%04X" % addr)
            dump.blocks.append((addr, bytes(data)))
            addr = None
        else:
            raise SysexError("unknown tag 0x%02X" % tag)
    return dump


def _put(out, tag, value):
    out += bytes((tag, 0x20 | (value >> 4), 0x10 | (value & 15)))


def build(dump):
    """The bytes of a dump, laid out as the UC4 itself sends them."""
    out = bytearray([0xF0]) + bytes(LEAD_ZEROS)
    _put(out, TAG_DEVICE, dump.device)
    _put(out, TAG_DUMP_TYPE, dump.dump_type)
    _put(out, TAG_VERSION_MAJOR, dump.firmware[0])
    _put(out, TAG_VERSION_MINOR, dump.firmware[1])
    for addr, data in dump.blocks:
        _put(out, TAG_ADDR_HIGH, addr >> 8)
        _put(out, TAG_ADDR_LOW, addr & 0xFF)
        for value in data:
            _put(out, TAG_DATA, value)
        checksum = sum(data)
        _put(out, TAG_CHECKSUM_HIGH, checksum >> 8)
        _put(out, TAG_CHECKSUM_LOW, checksum & 0xFF)
        out += bytes(BLOCK_GAP)
    _put(out, TAG_END, DEVICE_UC4)
    out.append(0xF7)
    return bytes(out)
