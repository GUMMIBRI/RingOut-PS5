# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-image DXT1/CMPR conversion; layout informed by GPL-3.0-or-later
C:/SC2/tools/guests/textures.py, cmpr_blocks and _reverse_pairs.

DXT1 is row-major 4x4 blocks; CMPR stores four blocks per 8x8 tile in
TL, TR, BL, BR order. Missing whole edge blocks are zero-filled; texels
outside the image within a present block are preserved verbatim.
"""


def _sizes(width, height):
    # GX TEX_IMAGE0 stores each dimension minus one in ten bits.
    if any(type(v) is not int or not 1 <= v <= 1024 for v in (width, height)):
        raise ValueError('width and height must be integers from 1 through 1024')
    bw, bh = (width + 3) // 4, (height + 3) // 4
    return bw, bh, bw * bh * 8, ((bw + 1) // 2) * ((bh + 1) // 2) * 32


def _reverse_pairs(value):
    return ((value & 3) << 6) | ((value & 12) << 2) | ((value & 48) >> 2) | ((value & 192) >> 6)


def _convert_block(block):
    # Endpoint byte swap and row index reversal are involutions.
    return bytes((block[1], block[0], block[3], block[2],
                  *(_reverse_pairs(x) for x in block[4:8])))


def _convert(data, width, height, to_cmpr):
    bw, bh, dxt_size, cmpr_size = _sizes(width, height)
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('data must be bytes-like')
    size = data.nbytes if isinstance(data, memoryview) else len(data)
    if size != (dxt_size if to_cmpr else cmpr_size):
        raise ValueError('incorrect image data length')
    # Reject oversized input before copying; memoryviews can have non-byte
    # elements, so their element count is not their encoded image size.
    data = bytes(data)
    out = bytearray(cmpr_size if to_cmpr else dxt_size)
    tile_offset = 0
    for ty in range(0, bh, 2):
        for tx in range(0, bw, 2):
            for sub in range(4):
                bx, by = tx + (sub & 1), ty + (sub >> 1)
                if bx < bw and by < bh:
                    linear = (by * bw + bx) * 8
                    source, dest = (linear, tile_offset) if to_cmpr else (tile_offset, linear)
                    out[dest:dest + 8] = _convert_block(data[source:source + 8])
                tile_offset += 8
    return bytes(out)


def dxt1_to_cmpr(data, width, height):
    """Convert exactly one DXT1 image, filling absent tile blocks with zero."""
    return _convert(data, width, height, True)


def cmpr_to_dxt1(data, width, height):
    """Convert exactly one CMPR image, ignoring whole tile padding blocks."""
    return _convert(data, width, height, False)
