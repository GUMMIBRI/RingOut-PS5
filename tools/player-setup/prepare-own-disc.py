"""Extract the player's US GameCube program for a local PS5 AOT build.

This script contains no original game data or generated code. It accepts only
plain GameCube ISO input. Extracted output belongs to the player and stays local.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

MAX_DOL = 64 * 1024 * 1024

def inspect_disc(image):
    image = Path(image)
    with image.open('rb') as src:
        header = src.read(0x440)
        if len(header) != 0x440 or header[0x1c:0x20] != bytes.fromhex('c2339f3d'):
            raise ValueError('Use a plain, uncompressed GameCube ISO from your own disc.')
        if header[:6] != b'GRSEAF':
            raise ValueError('This PS5 preparation step supports Soulcalibur II USA (GRSEAF) only.')
        dol_offset = struct.unpack_from('>I', header, 0x420)[0]
        image_size = os.fstat(src.fileno()).st_size
        if dol_offset < 0x440 or dol_offset > image_size - 0x100:
            raise ValueError('Disc program offset is outside the image.')
        src.seek(dol_offset)
        dol_header = src.read(0x100)
        offsets = struct.unpack_from('>18I', dol_header, 0)
        sizes = struct.unpack_from('>18I', dol_header, 0x90)
        used = [(off, size) for off, size in zip(offsets, sizes) if size]
        if not used or any(off < 0x100 or off + size > MAX_DOL for off, size in used):
            raise ValueError('Disc program sections are invalid or exceed the preparation limit.')
        ranges = sorted((off, off + size) for off, size in used)
        if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
            raise ValueError('Disc program sections overlap.')
        length = max(end for _, end in ranges)
        if length > image_size - dol_offset:
            raise ValueError('Disc program extends past the image.')
        src.seek(dol_offset)
        data = src.read(length)
        if len(data) != length:
            raise ValueError('Disc image changed or was truncated while reading its program.')
    return data, dict(game_id='GRSEAF', image_bytes=image_size, dol_offset=dol_offset,
                      dol_bytes=length, dol_sha256=hashlib.sha256(data).hexdigest(),
                      entry_point=hex(struct.unpack_from('>I', dol_header, 0xe0)[0]))

def prepare(image, output):
    # Require a new directory. Never replace an existing program, save or preparation.
    data, info = inspect_disc(image)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    program = output / 'main.dol'
    with program.open('xb') as dst:
        dst.write(data)
    info.update(stage='player-owned-disc-program-prepared', original_game_content=True,
                redistribution='Keep this output private; supply your own disc when rebuilding.',
                next_step='Run the source-matched DolRecomp generator, then compile its PS5 static module and link a local eboot. This script does not yet provide those build steps.')
    (output / 'PREPARE.json').write_text(json.dumps(info, indent=2) + '\n')
    return info

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        info = prepare(args.iso, args.out)
    except (OSError, ValueError) as error:
        parser.exit(2, f'Cannot prepare disc: {error}\n')
    print(json.dumps(info, indent=2))

if __name__ == '__main__':
    main()
