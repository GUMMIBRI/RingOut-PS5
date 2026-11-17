# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only SC2 archive inventory. Format informed by tools/guests/olnk.py and
roster.py in the local Xbox project (GPL-3.0-or-later). No assets are extracted.
"""
import argparse
import hashlib
import json
import mmap
import struct
from pathlib import Path


class FormatError(ValueError):
    pass


class Olnk:
    """A bounded view into an mmap or bytes object; nested views share storage."""
    def __init__(self, data, base=0, size=None):
        self.data = data
        self.base = base
        self.size = len(data) - base if size is None else size
        if base < 0 or self.size < 0 or base > len(data) or self.size > len(data) - base:
            raise FormatError('container outside backing data')
        if self.size < 32 or data[base + 4:base + 8] != b'olnk':
            raise FormatError('truncated or invalid OLNK header')
        self.count = struct.unpack_from('<I', data, base)[0]
        self.alignment = struct.unpack_from('<I', data, base + 8)[0]
        self.header_size, self.data_size = struct.unpack_from('<II', data, base + 16)
        if self.count > (self.size - 32) // 16:
            raise FormatError('OLNK table exceeds container')
        if self.header_size < 32 + self.count * 16 or self.header_size > self.size:
            raise FormatError('invalid OLNK header size')
        if self.data_size and self.data_size > self.size - self.header_size:
            raise FormatError('OLNK data size exceeds container')
        limit = self.data_size or (self.size - self.header_size)
        for i in range(self.count):
            offset, length, _, _ = struct.unpack_from('<IIII', data, base + 32 + i * 16)
            # Zero-sized entries are holes; their unused offsets need not be meaningful.
            if length and (offset > limit or length > limit - offset):
                raise FormatError('OLNK entry %d exceeds parent data' % i)

    def entry(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        offset, length, timestamp, _ = struct.unpack_from('<IIII', self.data, self.base + 32 + index * 16)
        return self.base + self.header_size + offset, length, timestamp

    def child(self, index):
        at, length, _ = self.entry(index)
        if not length:
            raise FormatError('hole cannot be a container')
        return Olnk(self.data, at, length)


def pack_parts(data, base, size, byte_order):
    """Return bounded (absolute offset, size) parts, or None for non-packs."""
    if byte_order not in ('big', 'little'):
        raise ValueError('byte_order must be big or little')
    if base < 0 or size < 0 or base > len(data) or size > len(data) - base:
        raise FormatError('pack outside backing data')
    if size < 8:
        return None
    order = '>' if byte_order == 'big' else '<'
    count = struct.unpack_from(order + 'I', data, base)[0]
    if count == 0 or count > 4096 or count > (size - 8) // 4:
        return None
    table_end = 8 + count * 4
    offsets = struct.unpack_from(order + str(count + 1) + 'I', data, base + 4)
    if offsets[0] < table_end or offsets[-1] > size or any(a > b for a, b in zip(offsets, offsets[1:])):
        return None
    return [(base + a, b - a) for a, b in zip(offsets, offsets[1:])]


def describe(data, at, size, byte_order):
    if not size:
        return {'size': 0, 'hole': True}
    view = memoryview(data)[at:at + size]
    try:
        result = {'size': size, 'magic_hex': bytes(view[:16]).hex(), 'sha256': hashlib.sha256(view).hexdigest()}
    finally:
        view.release()
    parts = pack_parts(data, at, size, byte_order)
    if parts is not None:
        result['possible_numbered_pack'] = [describe_part(data, pos, length) for pos, length in parts]
    return result


def describe_part(data, at, size):
    view = memoryview(data)[at:at + size]
    try:
        return {'size': size, 'magic_hex': bytes(view[:16]).hex(), 'sha256': hashlib.sha256(view).hexdigest()}
    finally:
        view.release()


def inventory(data, platform):
    if platform not in ('gamecube', 'xbox'):
        raise ValueError('unknown platform')
    order = 'big' if platform == 'gamecube' else 'little'
    root = Olnk(data)
    fighters, ui = root.child(4), root.child(2)
    blocks = []
    for block in range(max(0, (fighters.count - 46) // 39)):
        start = 46 + 39 * block
        slots = []
        for slot in range(39):
            at, size, _ = fighters.entry(start + slot)
            slots.append({'slot': slot, 'index': start + slot, **describe(data, at, size, order)})
        blocks.append({'block': block, 'start': start, 'slots': slots})
    # Source-derived resource indices are UI indices, not runtime fighter IDs.
    ui_indices = [5, 9, 10, 84, 85, 86, 146, 147, 148, 178, 179, 180,
                  284, 285, 286, 422, 423, 424, 470, 471, 472, 473, 474, 475, 476, 477]
    resources = {}
    for index in ui_indices:
        if index < ui.count:
            at, size, _ = ui.entry(index)
            resources[str(index)] = describe(data, at, size, order)
    return {'platform_choice': platform, 'child_pack_byte_order': order,
            'note': 'Platform is supplied by caller, not verified by archive. Pack recognition is heuristic; other block-to-fighter mappings are unknown.',
            'known_fighter_ids': {'Link': 27, 'Heihachi': 28, 'Spawn': 29},
            'stock_guest': {'block': 23, 'fighter': 'Link' if platform == 'gamecube' else 'Spawn',
                            'fighter_id': 27 if platform == 'gamecube' else 29,
                            'qualification': 'expected for stock platform archive; not verified by archive identity'},
            'ui_resource_indices_are_not_fighter_ids': True,
            'root_entry_count': root.count, 'character_entry_count': fighters.count,
            'complete_blocks': blocks, 'trailing_character_entries': max(0, (fighters.count - 46) % 39),
            'select_resources': resources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--platform', required=True, choices=('gamecube', 'xbox'))
    args = parser.parse_args()
    try:
        with args.archive.open('rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
                json.dump(inventory(data, args.platform), __import__('sys').stdout, indent=2)
                print()
    except (OSError, ValueError) as exc:
        parser.exit(2, 'inventory: %s\n' % exc)


if __name__ == '__main__':
    main()
