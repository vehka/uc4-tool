"""Setup files: a setup written as YAML. See docs/setup-file.md."""

import json
from collections import Counter

import yaml

from . import codes
from .setup import CONTROLS, GROUPS, KINDS, Control, Setup

FORMAT = 1
FIELDS = ("type", "channel", "number", "min", "max", "mode", "display")

# what a control listed in a setup file sends, unless the file says more
DEFAULTS = {
    "enc": {"type": "cc", "mode": "acc3", "display": "std", "min": 0, "max": 127},
    "push": {"type": "cc", "mode": "momentary", "display": 0, "min": 0, "max": 127},
    "button": {"type": "cc", "mode": "momentary", "display": "std", "min": 0, "max": 127},
    "fader": {"type": "cc", "mode": "jump", "display": "std", "min": 0, "max": 127},
}
# what a control left out of a setup file sends. buttons send nothing.
# encoders and faders can't be off: they send a controller no MIDI
# device should know, on channel 16, with nothing on the display
UNUSED = {
    "enc": {"type": "cc", "channel": 16, "number": 119, "mode": "acc0",
            "display": "off", "min": 0, "max": 127},
    "push": {"type": "off", "number": 0, "mode": "momentary", "display": 0,
             "min": 0, "max": 127},
    "button": {"type": "off", "number": 0, "mode": "momentary",
               "display": "off", "min": 0, "max": 127},
    "fader": {"type": "cc", "channel": 16, "number": 119, "mode": "jump",
              "display": "off", "min": 0, "max": 127},
}
# other ways to write a field
ALIASES = {"led": "display", "low": "min", "high": "max", "lower": "min",
           "upper": "max", "ch": "channel"}
# shorthands that give the type and the number at once
TYPE_SHORTHANDS = ("cc", "note", "cc14")
IGNORED = ("label",)


# words YAML reads as something else than text
YAML_WORDS = ("off", "on", "yes", "no", "true", "false", "null", "y", "n")


class SetupFileError(ValueError):
    pass


def _spec(value, kind, where):
    """A control as written in the file -> dict of fields."""
    if isinstance(value, bool) or not isinstance(value, (int, dict)):
        raise SetupFileError("%s: expected a number or a mapping, got %r"
                             % (where, value))
    if isinstance(value, int):
        return {"number": value}
    spec = {}
    for key, v in value.items():
        key = ALIASES.get(key, key)
        if key in TYPE_SHORTHANDS:
            if key not in codes.TYPES[kind]:
                raise SetupFileError("%s: %s can't send %s" % (where, kind, key))
            spec["type"], spec["number"] = key, v
        elif key in FIELDS:
            spec[key] = v
        elif key not in IGNORED:
            raise SetupFileError("%s: unknown field %r" % (where, key))
    return spec


def _control(spec, kind, where):
    """Resolved fields -> Control, checked."""
    for name in FIELDS:
        if name not in spec:
            raise SetupFileError("%s: no %s given" % (where, name))
    try:
        control = Control(
            type=codes.code_of(codes.TYPES[kind], spec["type"], "type"),
            channel=spec["channel"], number=spec["number"],
            low=spec["min"], high=spec["max"],
            mode=codes.code_of(codes.MODES[kind], spec["mode"], "mode"),
            display=codes.code_of(codes.DISPLAYS[kind], spec["display"], "display"))
    except ValueError as e:
        raise SetupFileError("%s: %s" % (where, e))
    for name, value, lo, hi in (("channel", control.channel, 1, 16),
                                ("number", control.number, 0, 127),
                                ("min", control.low, 0, 127),
                                ("max", control.high, 0, 127)):
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise SetupFileError("%s: %s must be %d to %d, got %r"
                                 % (where, name, lo, hi, value))
    if kind == "enc" and spec["type"] == "cc14" and control.number > 31:
        raise SetupFileError("%s: a 14 bit controller needs a number from 0 to 31 "
                             "(the UC4 sends the low byte on number + 32)" % where)
    return control


def parse(text):
    """The text of a setup file -> Setup."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SetupFileError("not valid YAML: %s" % e)
    if not isinstance(doc, dict):
        raise SetupFileError("a setup file is a mapping")
    known = ("uc4", "name", "firmware", "channel", "defaults", "unused",
             "encoder_groups", "fader_groups")
    for key in doc:
        if key not in known:
            raise SetupFileError("unknown key %r" % key)
    if doc.get("uc4", FORMAT) != FORMAT:
        raise SetupFileError("this is format %r, the tool knows format %d"
                             % (doc.get("uc4"), FORMAT))

    channel = doc.get("channel", 1)
    used, unused = {}, {}
    for kind in KINDS:
        used[kind] = dict(DEFAULTS[kind], channel=channel)
        used[kind].update(_spec((doc.get("defaults") or {}).get(kind) or {},
                                kind, "defaults." + kind))
        unused[kind] = dict(UNUSED[kind])
        unused[kind].setdefault("channel", channel)
        unused[kind].update(_spec((doc.get("unused") or {}).get(kind) or {},
                                  kind, "unused." + kind))

    def resolve(value, kind, where):
        if value is None:
            return _control(unused[kind], kind, where)
        return _control(dict(used[kind], **_spec(value, kind, where)), kind, where)

    def groups(key):
        value = doc.get(key) or []
        if not isinstance(value, list) or len(value) > GROUPS:
            raise SetupFileError("%s is a list of up to %d groups" % (key, GROUPS))
        return value + [{}] * (GROUPS - len(value))

    def controls(group, kind, where):
        value = group.get(kind) or []
        if not isinstance(value, list) or len(value) > CONTROLS:
            raise SetupFileError("%s is a list of up to %d controls" % (where, CONTROLS))
        value = value + [None] * (CONTROLS - len(value))
        return [resolve(v, kind, "%s %d" % (where, n + 1))
                for n, v in enumerate(value)]

    version = str(doc.get("firmware", "2.03")).split(".")
    try:
        setup = Setup(firmware=(int(version[0]), int(version[1])))
    except (ValueError, IndexError):
        raise SetupFileError("firmware is written like \"2.03\"")
    for kind in KINDS:
        setup.controls[kind] = []
    for g, group in enumerate(groups("encoder_groups")):
        where = "encoder group %d" % (g + 1)
        _check_keys(group, ("name", "enc", "push"), where)
        try:
            setup.names.append(codes.encode_name(group.get("name", "GrP%d" % (g + 1))))
        except ValueError as e:
            raise SetupFileError("%s: %s" % (where, e))
        setup.controls["enc"] += controls(group, "enc", where + " enc")
        setup.controls["push"] += controls(group, "push", where + " push")
    for g, group in enumerate(groups("fader_groups")):
        where = "fader group %d" % (g + 1)
        _check_keys(group, ("fader", "fader9", "button"), where)
        setup.controls["fader"] += controls(group, "fader", where + " fader")
        setup.controls["button"] += controls(group, "button", where + " button")
        setup.fader9.append(resolve(group.get("fader9"), "fader", where + " fader9"))
    return setup


def _check_keys(group, allowed, where):
    if not isinstance(group, dict):
        raise SetupFileError("%s: expected a mapping" % where)
    for key in group:
        if key not in allowed:
            raise SetupFileError("%s: unknown key %r" % (where, key))


def _fields(control, kind):
    return {
        "type": codes.name_of(codes.TYPES[kind], control.type),
        "channel": control.channel,
        "number": control.number,
        "min": control.low,
        "max": control.high,
        "mode": codes.name_of(codes.MODES[kind], control.mode),
        "display": codes.name_of(codes.DISPLAYS[kind], control.display),
    }


def _flow(value):
    """A value in YAML flow style, on one line."""
    if isinstance(value, dict):
        return "{" + ", ".join("%s: %s" % (k, _flow(v)) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    if isinstance(value, str):
        plain = value.isidentifier() and value.lower() not in YAML_WORDS
        return value if plain else json.dumps(value)
    return json.dumps(value)


def dump(setup, name=None):
    """A Setup -> the text of a setup file that gives the same setup."""
    fields = {kind: [_fields(c, kind) for c in setup.controls[kind]] for kind in KINDS}
    fader9 = [_fields(c, "fader") for c in setup.fader9]
    everything = [f for kind in KINDS for f in fields[kind]] + fader9
    channel = Counter(f["channel"] for f in everything).most_common(1)[0][0]

    # the most common value of each field becomes the default of its kind
    defaults = {}
    for kind in KINDS:
        pool = fields[kind] + (fader9 if kind == "fader" else [])
        defaults[kind] = {
            name_: Counter(json.dumps(f[name_]) for f in pool).most_common(1)[0][0]
            for name_ in FIELDS if name_ not in ("number", "channel")}
        defaults[kind] = {k: json.loads(v) for k, v in defaults[kind].items()}
        defaults[kind]["channel"] = Counter(
            f["channel"] for f in pool).most_common(1)[0][0]

    def short(f, kind):
        diff = {k: v for k, v in f.items()
                if k != "number" and defaults[kind][k] != v}
        if not diff:
            return f["number"]
        return dict({"number": f["number"]}, **diff)

    lines = ["uc4: %d" % FORMAT]
    if name:
        lines.append("name: %s" % _flow(name))
    lines.append("firmware: \"%d.%02d\"" % tuple(setup.firmware))
    lines.append("channel: %d" % channel)
    lines.append("")
    lines.append("defaults:")
    for kind in KINDS:
        d = {k: v for k, v in defaults[kind].items()
             if k != "channel" or v != channel}
        lines.append("  %s: %s" % (kind, _flow(d)))
    lines.append("")
    lines.append("encoder_groups:")
    for g in range(GROUPS):
        row = slice(g * CONTROLS, (g + 1) * CONTROLS)
        name_ = codes.decode_name(setup.names[g])
        # always quoted: a name like 1234 or "on" must stay text
        lines.append("  - name: %s" % (json.dumps(name_) if isinstance(name_, str)
                                       else _flow(name_)))
        lines.append("    enc:  %s" % _flow([short(f, "enc") for f in fields["enc"][row]]))
        lines.append("    push: %s" % _flow([short(f, "push") for f in fields["push"][row]]))
    lines.append("")
    lines.append("fader_groups:")
    for g in range(GROUPS):
        row = slice(g * CONTROLS, (g + 1) * CONTROLS)
        lines.append("  - fader:  %s" % _flow([short(f, "fader") for f in fields["fader"][row]]))
        lines.append("    fader9: %s" % _flow(short(fader9[g], "fader")))
        lines.append("    button: %s" % _flow([short(f, "button") for f in fields["button"][row]]))
    return "\n".join(lines) + "\n"
