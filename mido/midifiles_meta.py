"""
Meta messages for MIDI files.

Todo:
     - what if an unknown meta message is implemented and someone depends on
       the 'data' attribute?
     - 'byte' should be renamed to something more meaningful.
     - 'values' is not a good name for a dictionary.
     - type and value safety?
     - copy().
     - expose _key_signature_lookup?
"""
from __future__ import print_function, division
import sys
from .messages import BaseMessage
from .types import signed, unsigned

PY2 = (sys.version_info.major == 2)

_key_signature_lookup = {
        (-7, 0): ('Cb', 'major'),
        (-6, 0): ('Gb', 'major'),
        (-5, 0): ('Db', 'major'),
        (-4, 0): ('Ab', 'major'),
        (-3, 0): ('Eb', 'major'),
        (-2, 0): ('Bb', 'major'),
        (-1, 0): ('F', 'major'),
        (0, 0): ('C', 'major'),
        (1, 0): ('G', 'major'),
        (2, 0): ('D', 'major'),
        (3, 0): ('A', 'major'),
        (4, 0): ('E', 'major'),
        (5, 0): ('B', 'major'),
        (6, 0): ('F#', 'major'),
        (7, 0): ('C#', 'major'),
        (-7, 1): ('Ab', 'minor'),
        (-6, 1): ('Eb', 'minor'),
        (-5, 1): ('Bb', 'minor'),
        (-4, 1): ('F', 'minor'),
        (-3, 1): ('C', 'minor'),
        (-2, 1): ('G', 'minor'),
        (-1, 1): ('D', 'minor'),
        (0, 1): ('A', 'minor'),
        (1, 1): ('E', 'minor'),
        (2, 1): ('B', 'minor'),
        (3, 1): ('F#', 'minor'),
        (4, 1): ('C#', 'minor'),
        (5, 1): ('G#', 'minor'),
        (6, 1): ('D#', 'minor'),
        (7, 1): ('A#', 'minor'),
    }


def encode_text(text):
    return [ord(char) for char in text]  

def decode_text(data):
        # Todo: which encoding?
    if PY2:
        convert = unichr
    else:
        convert = chr

    text = ''.join([convert(byte) for byte in data])
    return text


def encode_tempo(tempo):
    return [tempo >> 16, tempo >> 8 & 0xff, tempo & 0xff]

def decode_tempo(data):
    return (data[0] << 16) | (data[1] << 8) | (data[2])

class MetaSpec(object):
    pass

class MetaSpec_text(MetaSpec):
    byte = 0x01
    attributes = ['text']
    defaults = ['']

    def encode(self, values):
        return encode_text(values['text'])

    def decode(self, data):
        return {'text': decode_text(data)}

class MetaSpec_copyright(MetaSpec_text):
    byte = 0x02

class MetaSpec_track_name(MetaSpec):
    byte = 0x03
    attributes = ['name']
    defaults = ['']
    
    def encode(self, values):
        return encode_text(values['name'])

    def decode(self, data):
        return {'name': decode_text(data)}

class MetaSpec_midi_port(MetaSpec):
    byte = 0x21
    attributes = ['port']
    defaults = [0]

    def encode(self, values):
        return [values['port']]

    def decode(self, data):
        return {'port': data[0]}

class MetaSpec_end_of_track(MetaSpec):
    byte = 0x2f
    attributes = []
    defaults = []

    def encode(self, values):
        return []

    def decode(self, data):
        return {}

class MetaSpec_set_tempo(MetaSpec):
    byte = 0x51
    attributes = ['tempo']
    defaults = [500000]

    def encode(self, values):
        return encode_tempo(values['tempo'])

    def decode(self, data):
        return {'tempo': decode_tempo(data)}

class MetaSpec_time_signature(MetaSpec):
    byte = 0x58
    attributes = ['numerator',
                  'denominator',
                  'clocks_per_click',
                  'notatated_32nd_notes_per_beat']
    defaults = [0, 0, 0, 0]

    def encode(self, values):
        return [values[name] for name in self.attributes]

    def decode(self, data):
        # Todo: NEEDS WORK
        # data[0] = numerator of time signature
        # data[1] = denominator of time signature
        # data[2] = number of MIDI clocks in metronome click
        #           (erm... yeahhh....)
        # data[3] = "number of notated 32nd notes in a MIDI quarter note"

        # message.time_numerator =
        # message.time_denominator =
        # message.clocks_per_click =
        # message. NOT SURE FOR THIS ONE

        return {name: value for (name, value) in zip(self.attributes, data)}

class MetaSpec_key_signature(MetaSpec):
    byte = 0x59
    attributes = ['key', 'mode']
    defaults = ['C', 'minor']

    def encode(self, values):
        return [unsigned('byte', values['key']), values['mode']]

    def decode(self, data):
        return {'key': signed('byte', data[0]),
                'mode': data[1]}

_specs = {}

# Todo: rethink this before launch.
#       Should this take an object or a class?
def add_meta_spec(klass):
    spec = klass()
    if not hasattr(spec, 'type'):
        name = klass.__name__.replace('MetaSpec_', '')
        spec.type = name
    _specs[spec.byte] = spec
    _specs[spec.type] = spec
    
def _add_builtin_meta_specs():
    for name in globals():
        if name.startswith('MetaSpec_'):
            add_meta_spec(globals()[name])

_add_builtin_meta_specs()


def _build_meta_message(type_, data):
    # Todo: handle unknown type.
    try:
        spec = _specs[type_]
    except KeyError:
        return UnknownMetaMessage(type_, data)

    return MetaMessage(spec, **spec.decode(data))

class MetaMessage(BaseMessage):
    def __init__(self, type_, **kwargs):
        # Todo: allow type_ to be a type byte?
        # Todo: handle unknown type.
        if isinstance(type_, MetaSpec):
            self._spec = type_
        else:
            self._spec = _specs[type_]

        self.type = self._spec.type

        for name in kwargs:
            if name == 'time':
                continue  # Time is always allowed.

            if name not in self._spec.attributes:
                raise ValueError(
                    '{} is not a valid argument for this message type'.format(
                        name))

        for name, value in zip(self._spec.attributes, self._spec.defaults):
            setattr(self, name, value)
        self.time = 0

        self.__dict__.update(kwargs)

    def bytes(self):
        data = self._spec.encode(self.__dict__)
        return [0xff, len(data)] + data
    
    def __repr__(self):
        attributes = []
        for name in self._spec.attributes:
            attributes.append('{}={!r}'.format(name, getattr(self, name)))
        attributes = ', '.join(attributes)
        if attributes:
            attributes = (' {}'.format(attributes))

        return '<meta message {}{} time={}>'.format(self.type,
                                                    attributes, self.time)

# Todo: what if one of these messages is implemented?
class UnknownMetaMessage(MetaMessage):
    def __init__(self, type_, data=None, time=0):
        if data is None:
            data = []

        self.type = 'unknown'
        self.byte = type_
        self.data = data
        self.time = time

    def __repr__(self):
        return '<unknown meta message 0x{:02x} data={!r}'.format(self.byte,
                                                                self.data)

    def bytes(self):
        return [0xff, len(self.data)] + self.data

