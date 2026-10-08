"""Names of the codes in a setup. The position in a list is the code."""

TYPES = {
    "enc": ["cc_rel1", "cc_rel2", "cc", "program", "cc14", "pitchbend",
            "aftertouch"],
    "push": ["off", "note", "cc", "program", "aftertouch"],
    "button": ["off", "note", "cc", "program", "aftertouch"],
    "fader": ["cc", "program", "pitchbend", "aftertouch"],
}
MODES = {
    "enc": ["acc0", "acc1", "acc2", "acc3"],
    "push": ["momentary", "toggle"],
    "button": ["momentary", "toggle"],
    "fader": ["jump", "snap"],
}
# the display of an encoder or fader, the LED of a green button. the
# code of an encoder push button has no known meaning
DISPLAYS = {
    "enc": ["off", "std", "bipolar"],
    "push": [],
    "button": ["off", "std", "ext"],
    "fader": ["off", "std", "bipolar"],
}

# the characters of the 4 digit display, by code
CHARSET = "0123456789AbCdEFGHIJLMnOPqrStUXyZ-_'\"= "
BLANK = CHARSET.index(" ")


def name_of(table, code):
    """The name of a code, or the code itself when it has none."""
    return table[code] if 0 <= code < len(table) else code


def code_of(table, value, what):
    """The code of a name. A number is taken as the code."""
    if value is False and "off" in table:
        value = "off"  # YAML reads a bare off as false
    if isinstance(value, bool):
        raise ValueError("%s can't be %r" % (what, value))
    if isinstance(value, int):
        if not 0 <= value <= 15:
            raise ValueError("%s code %d is out of range" % (what, value))
        return value
    if value in table:
        return table.index(value)
    raise ValueError("unknown %s %r (known: %s)"
                     % (what, value, ", ".join(table) or "numbers only"))


def decode_name(chars):
    """Character codes to text, or the codes when one has no character."""
    if all(0 <= c < len(CHARSET) for c in chars):
        return "".join(CHARSET[c] for c in chars)
    return list(chars)


def encode_name(name, length=4):
    if isinstance(name, list):
        codes = list(name)
    else:
        codes = []
        for ch in str(name):
            # the display has one shape for a letter, in one case
            for candidate in (ch, ch.upper(), ch.lower()):
                if candidate in CHARSET:
                    codes.append(CHARSET.index(candidate))
                    break
            else:
                raise ValueError("the display has no character %r (it has: %s)"
                                 % (ch, CHARSET))
    if len(codes) > length:
        raise ValueError("the name %r is longer than %d characters" % (name, length))
    return codes + [BLANK] * (length - len(codes))
