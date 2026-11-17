# SPDX-License-Identifier: GPL-3.0-or-later
"""Endian conversion for SC2 motion and one-frame pose banks.

Adapted from C:/SC2/tools/guests/motion.py, SPDX GPL-3.0-or-later,
which documents the GameCube/Xbox format and shared-character comparisons.
Conversion is in memory only; the caller owns archive operations. Source byte
order is explicit: 'big' (GameCube) or 'little' (Xbox).
"""
import struct


def _order(source):
    if source == 'big':
        return '>'
    if source == 'little':
        return '<'
    raise ValueError("source must be 'big' or 'little'")


def motion_blocks(frames, flags):
    if flags & 8:
        frames = (frames + 3) // 4
    elif flags & 4:
        frames = (frames + 1) // 2
    return (frames + 7) // 8


def _swap(out, offset, width, count=1):
    for p in range(offset, offset + width * count, width):
        out[p:p + width] = out[p:p + width][::-1]


def convert_motion(data, source):
    """Convert a single motion to the opposite byte order, preserving padding."""
    endian = _order(source)
    data = bytes(data)
    if len(data) < 0x1c:
        raise ValueError('truncated motion header')
    frames, channel_bytes, flags = struct.unpack_from(endian + 'HHI', data)
    if channel_bytes % 2:
        raise ValueError('odd channel byte count')
    count = motion_blocks(frames, flags)
    table_end = 0x1c + 2 * count
    if table_end > len(data):
        raise ValueError('truncated motion block table')
    steps = struct.unpack_from(endian + str(count) + 'h', data, 0x1c)
    positions = []
    position = 0x1c
    previous_end = table_end
    for step in steps:
        position += step
        if position < previous_end or position + channel_bytes > len(data):
            raise ValueError('motion block overlaps header/table or previous block, or is outside motion')
        positions.append(position)
        previous_end = position + channel_bytes
    out = bytearray(data)
    _swap(out, 0, 2, 2)
    _swap(out, 4, 4)
    _swap(out, 8, 8)
    _swap(out, 0x10, 2)
    _swap(out, 0x1c, 2, count)
    for position in positions:
        _swap(out, position, 2, channel_bytes // 2)
    return bytes(out)


def _bank_offsets(data, source):
    endian = _order(source)
    if len(data) < 8:
        raise ValueError('truncated bank header')
    count = struct.unpack_from(endian + 'I', data)[0]
    if count > (len(data) - 8) // 4:
        raise ValueError('bank count exceeds offset table')
    table_end = 8 + 4 * count
    offsets = list(struct.unpack_from(endian + str(count) + 'I', data, 8))
    previous = table_end
    for offset in offsets:
        if offset < previous or offset > len(data):
            raise ValueError('bank offsets are nonmonotone or outside bank')
        previous = offset
    return offsets + [len(data)]


def convert_bank(data, source):
    """Convert an entire bank to opposite order; empty entries are retained."""
    data = bytes(data)
    offsets = _bank_offsets(data, source)
    out = bytearray(data)
    _swap(out, 0, 4, len(offsets) + 1)
    for a, b in zip(offsets, offsets[1:]):
        if a != b:
            out[a:b] = convert_motion(data[a:b], source)
    return bytes(out)


def convert_pose_bank(data, source):
    """Convert a one-frame pose bank, adjusting the platform-specific +0x18 field.

    The field is little-endian on both platforms, regardless of source order.
    Only observed non-wrapping +0x20 values are accepted.
    """
    data = bytes(data)
    endian = _order(source)
    offsets = _bank_offsets(data, source)
    adjustments = []
    for a, b in zip(offsets, offsets[1:]):
        if a == b:
            continue
        if b - a < 0x1c or struct.unpack_from(endian + 'H', data, a)[0] != 1:
            raise ValueError('unrecognized pose: expected a one-frame motion')
        value = struct.unpack_from('<H', data, a + 0x18)[0]
        if source == 'little':
            if value < 0x20:
                raise ValueError('unrecognized Xbox pose field below 0x20')
            value -= 0x20
        else:
            if value > 0xffff - 0x20:
                raise ValueError('GameCube pose field would overflow')
            value += 0x20
        adjustments.append((a + 0x18, value))
    out = bytearray(convert_bank(data, source))
    for offset, value in adjustments:
        struct.pack_into('<H', out, offset, value)
    return bytes(out)


def convert_moveset_tables(data, source):
    """Convert the numbered table pack within moveset part 2.

    Trailing incomplete records and camera words are padding and are retained.
    """
    data = bytes(data)
    endian = _order(source)
    if len(data) < 8:
        raise ValueError('truncated moveset table header')
    count = struct.unpack_from(endian + 'I', data)[0]
    if count > (len(data) - 8) // 4:
        raise ValueError('moveset table count exceeds offset table')
    offsets = struct.unpack_from(endian + str(count + 1) + 'I', data, 4)
    previous = 4 * (count + 2)
    for offset in offsets:
        if offset < previous or offset > len(data):
            raise ValueError('moveset table offsets are nonmonotone or outside pack')
        previous = offset
    out = bytearray(data)
    _swap(out, 0, 4, count + 2)
    for part, (start, end) in enumerate(zip(offsets, offsets[1:])):
        if part == 0:
            for record in range(start, end - 59, 60):
                _swap(out, record + 48, 2, 6)
        elif part == 1:
            if end - start < 8:
                raise ValueError('moveset part 1 header is truncated')
            _swap(out, start, 2, 2)
            _swap(out, start + 4, 4)
            for record in range(start + 8, end - 39, 40):
                _swap(out, record + 16, 2, 12)
        else:
            if end - start < 8:
                raise ValueError('camera track header is truncated')
            _swap(out, start, 2, 4)
            _swap(out, start + 8, 4, (end - start - 8) // 4)
    return bytes(out)


def convert_moveset(parts, source):
    """Convert populated bank/table parts while preserving other pack entries."""
    _order(source)
    out = list(parts)
    if len(out) > 1 and out[1]:
        out[1] = convert_bank(out[1], source)
    if len(out) > 2 and out[2]:
        out[2] = convert_moveset_tables(out[2], source)
    return out


def convert_moveset_pack(data, source):
    """Convert a numbered moveset pack in place within its original extents.

    The returned bytes retain header padding, part boundaries, and bytes after
    the final part. No target-loader alignment guarantees are implied.
    """
    endian = _order(source)
    data = bytes(data)
    if len(data) < 8:
        raise ValueError('truncated moveset pack header')
    count = struct.unpack_from(endian + 'I', data)[0]
    if count == 0 or count > 4096 or count > (len(data) - 8) // 4:
        raise ValueError('invalid moveset pack count or truncated offset table')
    offsets = struct.unpack_from(endian + str(count + 1) + 'I', data, 4)
    previous = 4 * (count + 2)
    for offset in offsets:
        if offset < previous or offset > len(data):
            raise ValueError('moveset pack offsets are nonmonotone or outside pack')
        previous = offset
    parts = [data[a:b] for a, b in zip(offsets, offsets[1:])]
    converted = convert_moveset(parts, source)
    if len(converted) != count or any(len(x) != len(y) for x, y in zip(parts, converted)):
        raise ValueError('moveset conversion changed part sizes')
    out = bytearray(data)
    _swap(out, 0, 4, count + 2)
    for a, b, part in zip(offsets, offsets[1:], converted):
        out[a:b] = part
    return bytes(out)


def gamecube_to_xbox_motion(data): return convert_motion(data, 'big')
def xbox_to_gamecube_motion(data): return convert_motion(data, 'little')
def gamecube_to_xbox_bank(data): return convert_bank(data, 'big')
def xbox_to_gamecube_bank(data): return convert_bank(data, 'little')
def gamecube_to_xbox_pose_bank(data): return convert_pose_bank(data, 'big')
def xbox_to_gamecube_pose_bank(data): return convert_pose_bank(data, 'little')
def gamecube_to_xbox_moveset_tables(data): return convert_moveset_tables(data, 'big')
def xbox_to_gamecube_moveset_tables(data): return convert_moveset_tables(data, 'little')
def gamecube_to_xbox_moveset(parts): return convert_moveset(parts, 'big')
def xbox_to_gamecube_moveset(parts): return convert_moveset(parts, 'little')
def gamecube_to_xbox_moveset_pack(data): return convert_moveset_pack(data, 'big')
def xbox_to_gamecube_moveset_pack(data): return convert_moveset_pack(data, 'little')
