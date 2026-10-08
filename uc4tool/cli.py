"""Command line: uc4 decode | encode | info | send | receive."""

import argparse
import sys

from . import __version__, midi, setup as setup_mod, setupfile, sysex

RECEIVE_HELP = """\
Put the UC4 in receive mode:
  1. hold shift and press edit twice (setup mode)
  2. select setup %d with encoder 1 (SE%02d)
  3. press encoder 7 and keep it down until the display shows rCOn
     (a short press only shows the function name, rEc, and the data is
     ignored)
The UC4 shows SE%02d when the setup is stored."""

SEND_HELP = """\
Make the UC4 send:
  1. hold shift and press edit twice (setup mode)
  2. one setup: select it with encoder 1, then hold encoder 4 (Sndc)
     all setups: hold encoder 8 (SndA)"""


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _write(path, data):
    if path in (None, "-"):
        out = sys.stdout.buffer if isinstance(data, bytes) else sys.stdout
        out.write(data)
        return
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)


def _is_sysex(data):
    return data[:1] == b"\xF0"


def _load_dump_bytes(path, slot):
    """The bytes to send for a .syx or setup file."""
    data = _read(path)
    if _is_sysex(data):
        dump = sysex.parse(data)  # checks it before it goes to the device
        if slot is None:
            return data, setup_mod.slots_in(dump)
        setup, _ = setup_mod.from_dump(dump, None if len(
            setup_mod.slots_in(dump)) == 1 else slot)
        return sysex.build(setup_mod.to_dump(setup, slot)), [slot]
    if slot is None:
        raise ValueError("give the setup number to send it to with --slot")
    setup = setupfile.parse(data.decode("utf-8"))
    return sysex.build(setup_mod.to_dump(setup, slot)), [slot]


def cmd_info(args):
    dump = sysex.parse(_read(args.file))
    kinds = {sysex.DUMP_ONE_SETUP: "one setup", sysex.DUMP_ALL_SETUPS: "all setups"}
    print("dump type: %s" % kinds.get(dump.dump_type, "0x%02X" % dump.dump_type))
    print("firmware:  %d.%02d" % dump.firmware)
    print("blocks:    %d (0x%04X to 0x%04X)" % (
        len(dump.blocks), dump.blocks[0][0],
        dump.blocks[-1][0] + len(dump.blocks[-1][1]) - 1))
    print("setups:    %s" % ", ".join(map(str, setup_mod.slots_in(dump))))


def cmd_decode(args):
    dump = sysex.parse(_read(args.file))
    setup, slot = setup_mod.from_dump(dump, args.slot)
    _write(args.output, setupfile.dump(setup, name=args.name or "setup %d" % slot))


def cmd_encode(args):
    setup = setupfile.parse(_read(args.file).decode("utf-8"))
    data = sysex.build(setup_mod.to_dump(setup, args.slot))
    if args.output in (None, "-") and sys.stdout.isatty():
        raise ValueError("give a file to write to with -o")
    _write(args.output, data)


def cmd_send(args):
    data, slots = _load_dump_bytes(args.file, args.slot)
    port = args.port or midi.find_port()
    if len(slots) == 1:
        print(RECEIVE_HELP % (slots[0], slots[0], slots[0]), file=sys.stderr)
        print("This overwrites setup %d." % slots[0], file=sys.stderr)
    else:
        print("This overwrites ALL %d setups of the UC4." % len(slots), file=sys.stderr)
        print("Put the UC4 in receive mode (setup mode, hold encoder 7 "
              "until the display shows rCOn).", file=sys.stderr)
    if not args.yes:
        if not sys.stdin.isatty():
            raise ValueError("not sent: confirm with --yes when the UC4 is "
                             "in receive mode")
        input("Press enter when the UC4 is in receive mode... ")
    midi.send(data, port)
    print("sent %d bytes to %s" % (len(data), port), file=sys.stderr)


def cmd_receive(args):
    port = args.port or midi.find_port()
    print(SEND_HELP, file=sys.stderr)
    print("Waiting %d seconds for a dump on %s..." % (args.wait, port),
          file=sys.stderr)
    data = midi.receive(port, wait=args.wait)
    dump = sysex.parse(data)
    _write(args.output, data)
    print("received %d bytes, setups: %s" % (
        len(data), ", ".join(map(str, setup_mod.slots_in(dump)))), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="uc4", description="Read, write and send Faderfox UC4 setups.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="show what a .syx dump holds")
    p.add_argument("file")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("decode", help="turn a .syx dump into a setup file")
    p.add_argument("file")
    p.add_argument("--slot", type=int,
                   help="which setup to take from a dump of all setups")
    p.add_argument("--name", help="name to write into the setup file")
    p.add_argument("-o", "--output", help="file to write (default: stdout)")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("encode", help="turn a setup file into a .syx dump")
    p.add_argument("file")
    p.add_argument("--slot", type=int, required=True,
                   help="setup number (1-18) the dump is made for")
    p.add_argument("-o", "--output", help="file to write")
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("send", help="send a setup file or .syx dump to the UC4")
    p.add_argument("file")
    p.add_argument("--slot", type=int,
                   help="setup number (1-18) to overwrite. needed for a setup "
                        "file; moves a one-setup dump to another setup")
    p.add_argument("--port", help="raw MIDI device (default: the first UC4)")
    p.add_argument("--yes", action="store_true",
                   help="the UC4 is in receive mode: send without asking")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("receive", help="save a dump the UC4 sends")
    p.add_argument("-o", "--output", required=True, help="file to write")
    p.add_argument("--port", help="raw MIDI device (default: the first UC4)")
    p.add_argument("--wait", type=int, default=60,
                   help="seconds to wait for the dump to start (default 60)")
    p.set_defaults(func=cmd_receive)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, midi.MidiError, OSError) as e:
        print("uc4: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
