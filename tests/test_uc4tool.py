"""Tests against dumps a UC4 (firmware 2.03) sent or accepted.

factory-setup-02.syx  setup 2 in its factory state, as sent by the UC4
norn-setup-16.syx     the setup of the norns-uc4 mod, accepted by the UC4
probe-setup-15.syx    a setup with every type, mode and display code,
                      accepted by the UC4; what its controls then sent
                      is how the codes in uc4tool/codes.py were confirmed
"""

from pathlib import Path

import pytest

from uc4tool import cli, codes, setup as setup_mod, setupfile, sysex

DATA = Path(__file__).parent / "data"
ROOT = Path(__file__).parent.parent
DUMPS = ["factory-setup-02.syx", "norn-setup-16.syx", "probe-setup-15.syx"]


def load(name):
    raw = (DATA / name).read_bytes()
    setup, slot = setup_mod.from_dump(sysex.parse(raw))
    return raw, setup, slot


@pytest.mark.parametrize("name", DUMPS)
def test_dump_round_trip(name):
    raw, setup, slot = load(name)
    assert sysex.build(sysex.parse(raw)) == raw
    assert sysex.build(setup_mod.to_dump(setup, slot)) == raw


@pytest.mark.parametrize("name", DUMPS)
def test_setup_file_round_trip(name):
    raw, setup, slot = load(name)
    again = setupfile.parse(setupfile.dump(setup))
    assert sysex.build(setup_mod.to_dump(again, slot)) == raw


def test_factory_setup():
    _, setup, slot = load("factory-setup-02.syx")
    assert slot == 2
    assert [codes.decode_name(n) for n in setup.names] == [
        "GrP%d" % g for g in range(1, 9)]
    # the manual: channel = setup number, encoders absolute, CC 8-15 in
    # group 1 and 72-79 in group 5, push buttons notes 0-7
    enc = setup.control("enc", 1, 1)
    assert (enc.type, enc.channel, enc.number, enc.low, enc.high) == (2, 2, 8, 0, 127)
    assert codes.name_of(codes.MODES["enc"], enc.mode) == "acc3"
    assert setup.control("enc", 5, 8).number == 79
    push = setup.control("push", 1, 8)
    assert codes.name_of(codes.TYPES["push"], push.type) == "note" and push.number == 7
    assert setup.control("button", 8, 8).number == 127
    assert setup.control("fader", 5, 1).number == 104
    assert [f.number for f in setup.fader9] == [112] * 8


def test_probe_setup_codes():
    _, setup, _ = load("probe-setup-15.syx")
    text = setupfile.dump(setup)
    assert setupfile.parse(text).controls == setup.controls
    types = [codes.name_of(codes.TYPES["enc"], setup.control("enc", 1, n).type)
             for n in range(1, 8)]
    assert types == codes.TYPES["enc"]
    assert [setup.control("button", 1, n).type for n in range(1, 6)] == [0, 1, 2, 3, 4]
    assert [setup.control("fader", 1, n).type for n in range(1, 5)] == [0, 1, 2, 3]
    assert [setup.control("enc", 2, n).mode for n in range(1, 5)] == [0, 1, 2, 3]
    assert [setup.control("enc", 2, n).display for n in range(5, 8)] == [0, 1, 2]


def test_one_setup_from_another_slot():
    raw, setup, _ = load("factory-setup-02.syx")
    moved = sysex.parse(sysex.build(setup_mod.to_dump(setup, 9)))
    assert setup_mod.slots_in(moved) == [9]
    assert setup_mod.from_dump(moved)[0].controls == setup.controls


def test_op1_field_setup():
    setup = setupfile.parse((ROOT / "setups" / "op1-field.yaml").read_text())
    assert codes.decode_name(setup.names[0]) == "Synt"
    assert [setup.control("enc", 1, n).number for n in range(1, 9)] == list(range(46, 54))
    pan = setup.control("enc", 4, 5)
    assert (pan.number, pan.channel, pan.display) == (10, 1, 2)
    mute = setup.control("button", 2, 3)
    assert (mute.number, mute.channel, mute.mode) == (9, 3, 1)
    slot8 = setup.control("button", 3, 8)
    assert (slot8.number, slot8.channel) == (102, 8)
    # the faders are the same in all groups
    assert all(setup.control("fader", g, 2).channel == 2 for g in range(1, 9))
    # what the file leaves out: buttons send nothing, encoders something harmless
    assert setup.control("push", 1, 1).type == 0
    assert setup.control("button", 8, 1).type == 0
    unused = setup.control("enc", 8, 1)
    assert (unused.number, unused.channel, unused.display) == (119, 16, 0)
    assert len(sysex.build(setup_mod.to_dump(setup, 3))) == 5072


def test_setup_file_shorthands():
    setup = setupfile.parse("""
channel: 5
defaults:
  enc: {mode: acc1}
unused:
  fader: {number: 3}
encoder_groups:
  - name: ab
    enc: [7, {cc14: 1, min: 10}, {type: pitchbend, number: 0}, ~, {cc: 9, ch: 2, label: x}]
    push: [{note: 60, mode: toggle, max: 100}, {type: off, number: 0}]
fader_groups:
  - button: [{cc: 1, led: ext}]
""")
    assert codes.decode_name(setup.names[0]) == "Ab  "
    a, b, c, d, e = (setup.control("enc", 1, n) for n in range(1, 6))
    assert (a.number, a.channel, a.type, a.mode) == (7, 5, 2, 1)
    assert (b.type, b.number, b.low) == (4, 1, 10)
    assert c.type == 5
    assert (d.number, d.channel) == (119, 16)        # left out with ~
    assert (e.number, e.channel) == (9, 2)
    push = setup.control("push", 1, 1)
    assert (push.type, push.number, push.mode, push.high) == (1, 60, 1, 100)
    assert setup.control("push", 1, 2).type == 0    # a bare off is YAML's false
    assert setup.control("button", 1, 1).display == 2
    assert setup.control("fader", 1, 1).number == 3 and setup.fader9[0].number == 3


@pytest.mark.parametrize("text, message", [
    ("encoder_groups: [{enc: [{cc14: 40}]}]", "14 bit"),
    ("encoder_groups: [{enc: [200]}]", "number must be"),
    ("encoder_groups: [{enc: [{cc: 1, speed: 3}]}]", "unknown field"),
    ("encoder_groups: [{enc: [{type: note, number: 1}]}]", "unknown type"),
    ("encoder_groups: [{name: toolong}]", "longer than"),
    ("encoder_groups: [{name: 'a?'}]", "no character"),
    ("fader_groups: [{fader: [{note: 1}]}]", "can't send"),
    ("channel: 17\nencoder_groups: [{enc: [1]}]", "channel must be"),
    ("groups: []", "unknown key"),
])
def test_setup_file_errors(text, message):
    with pytest.raises(setupfile.SetupFileError, match=message):
        setupfile.parse(text)


def test_bad_dumps():
    raw = bytearray((DATA / "factory-setup-02.syx").read_bytes())
    with pytest.raises(sysex.SysexError, match="not a sysex"):
        sysex.parse(b"hello")
    with pytest.raises(sysex.SysexError, match="cut short"):
        sysex.parse(bytes(raw[:2000]) + b"\xF7")
    raw[60] ^= 1    # a data nibble
    with pytest.raises(sysex.SysexError, match="checksum"):
        sysex.parse(bytes(raw))


def test_cli(tmp_path, capsys):
    syx, yml, back = tmp_path / "a.syx", tmp_path / "a.yaml", tmp_path / "b.syx"
    src = DATA / "norn-setup-16.syx"
    assert cli.main(["decode", str(src), "-o", str(yml)]) == 0
    assert cli.main(["encode", str(yml), "--slot", "16", "-o", str(back)]) == 0
    assert back.read_bytes() == src.read_bytes()
    assert cli.main(["encode", str(yml), "--slot", "4", "-o", str(syx)]) == 0
    assert cli.main(["info", str(syx)]) == 0
    assert "setups:    4" in capsys.readouterr().out
    assert cli.main(["encode", str(yml), "--slot", "19", "-o", str(syx)]) == 1
    # without a slot: the same setup, with the addresses of setup 1
    assert cli.main(["encode", str(yml), "-o", str(syx)]) == 0
    assert cli.main(["info", str(syx)]) == 0
    assert "setups:    1" in capsys.readouterr().out
    assert cli.main(["send", str(yml), "--port", "/dev/null"]) == 1
    assert "not sent" in capsys.readouterr().err
    # sending needs a confirmation that the UC4 is in receive mode
    assert cli.main(["send", str(yml), "--slot", "4", "--port", "/dev/null"]) == 1
    assert "not sent" in capsys.readouterr().err
