"""Talk to a UC4 over ALSA raw MIDI (Linux)."""

import glob
import os
import re
import select
import time

DEVICE_NAME = "UC4"

# the UC4 needs time to store each block of a dump. this is about half
# the speed of a MIDI cable, the pace the UC4 was seen to take dumps at
CHUNK_SIZE = 16
CHUNK_TIME = 0.01


class MidiError(RuntimeError):
    pass


def find_port():
    """The raw MIDI device of the first UC4, e.g. /dev/snd/midiC1D0."""
    try:
        with open("/proc/asound/cards") as f:
            cards = f.read()
    except OSError:
        raise MidiError("no ALSA sound system found (this needs Linux)")
    # a line per card: " 1 [UC4            ]: USB-Audio - Faderfox UC4"
    for card, name in re.findall(r"^\s*(\d+) \[(.*)$", cards, re.MULTILINE):
        if DEVICE_NAME in name:
            ports = sorted(glob.glob("/dev/snd/midiC%sD*" % card))
            if ports:
                return ports[0]
    raise MidiError("no UC4 found (is it plugged in?)")


def send(data, port=None, progress=None):
    """Send a dump at a pace the UC4 can take."""
    port = port or find_port()
    try:
        fd = os.open(port, os.O_WRONLY)
    except OSError as e:
        raise MidiError("can't open %s: %s" % (port, e.strerror))
    try:
        for i in range(0, len(data), CHUNK_SIZE):
            os.write(fd, data[i:i + CHUNK_SIZE])
            time.sleep(CHUNK_TIME)
            if progress:
                progress(min(i + CHUNK_SIZE, len(data)), len(data))
    finally:
        os.close(fd)


def receive(port=None, wait=60, progress=None):
    """Wait for the UC4 to send a dump and return its bytes."""
    port = port or find_port()
    try:
        fd = os.open(port, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as e:
        raise MidiError("can't open %s: %s" % (port, e.strerror))
    data = bytearray()
    deadline = time.time() + wait
    try:
        while True:
            # once the dump has started, a pause means it was cut off
            timeout = deadline - time.time() if not data else 3
            if timeout <= 0 or not select.select([fd], [], [], timeout)[0]:
                break
            for b in os.read(fd, 4096):
                if b >= 0xF8:
                    continue  # realtime messages can sit inside a sysex
                if b == 0xF0:
                    data = bytearray()
                if data or b == 0xF0:
                    data.append(b)
                if b == 0xF7 and data:
                    return bytes(data)
            if progress:
                progress(len(data))
    finally:
        os.close(fd)
    if data:
        raise MidiError("the dump stopped after %d bytes" % len(data))
    raise MidiError("nothing received in %d seconds" % wait)
