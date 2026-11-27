# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare or verify the private game folder for the RingOut US GameCube build."""
import argparse
import hashlib
import json
import os
import struct
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = json.loads((HERE / 'grseaf-files.json').read_text(encoding='utf-8'))
CHUNK = 1 << 20
sys.dont_write_bytecode = True


def require(test, message):
    if not test:
        raise ValueError(message)


def read_at(stream, offset, size):
    stream.seek(offset)
    result = stream.read(size)
    require(len(result) == size, 'GameCube image is incomplete')
    return result


def base_inputs(source):
    """Yield (published destination, local source, source offset) for one verified release."""
    if source.is_dir():
        for name, spec in BASE.items():
            path = source / name
            require(path.is_file() and path.stat().st_size == spec['bytes'],
                    f'Missing or wrong-size GameCube file: {path}')
            yield name, path, 0
        return

    require(source.is_file(), f'GameCube input does not exist: {source}')
    with source.open('rb') as f:
        boot = read_at(f, 0, 0x440)
        require(boot[:6] == b'GRSEAF' and boot[28:32] == bytes.fromhex('c2339f3d'),
                'Use the plain US GameCube ISO/GCM (GRSEAF), or a folder containing files/ and sys/.')
        dol, fst, fst_bytes = struct.unpack_from('>3I', boot, 0x420)
        require(fst_bytes == BASE['sys/fst.bin']['bytes'], 'GameCube file table size differs from the supported US disc')
        table = read_at(f, fst, fst_bytes)
        count = len([name for name in BASE if name.startswith('files/')]) + 1
        require(struct.unpack_from('>3I', table) == (1 << 24, 0, count), 'Unexpected GameCube file table')
        offsets = {'sys/boot.bin': 0, 'sys/bi2.bin': 0x440, 'sys/apploader.img': 0x2440,
                   'sys/main.dol': dol, 'sys/fst.bin': fst}
        for i in range(1,count):
            entry, start, size = struct.unpack_from('>3I', table, i*12)
            name_start = count*12 + entry
            end = table.find(b'\0',name_start)
            require(entry < (1 << 24) and 0 <= name_start < end, 'Invalid US disc filename')
            name = 'files/' + table[name_start:end].decode('ascii')
            require(name in BASE and name not in offsets and size == BASE[name]['bytes'],
                    f'Unexpected US GameCube file or size: {name}')
            offsets[name] = start
        require(offsets.keys() == BASE.keys(), 'Incomplete US GameCube file inventory')
        size = source.stat().st_size
        for name, start in offsets.items():
            require(start+BASE[name]['bytes'] <= size, f'GameCube image is incomplete at {name}')
            yield name, source, start


def process_base(source, destination=None):
    for name, path, start in base_inputs(source):
        remaining = BASE[name]['bytes']
        digest = hashlib.sha256()
        with ExitStack() as files:
            src = files.enter_context(path.open('rb'))
            src.seek(start)
            out = None
            if destination is not None:
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                out = files.enter_context(target.open('xb'))
            while remaining:
                block = src.read(min(remaining,CHUNK))
                require(block,f'Short read in {name}')
                remaining -= len(block)
                digest.update(block)
                if out:
                    out.write(block)
        require(digest.hexdigest() == BASE[name]['sha256'],
                f'{name} differs from the supported US GameCube release')


def ps2_files(path):
    import ps2iso
    import xiso
    if not path.is_dir():
        return ps2iso.open_image(path)
    files = {}
    required = {'ROOT.OLK',ps2iso.SLUS_20643.elf_name}
    for p in path.iterdir():
        name = p.name.removesuffix(';1').upper()
        if name in required and p.is_file():
            require(name not in files, f'Ambiguous extracted PS2 file: {name}')
            files[name] = xiso.FileView(str(p),0,p.stat().st_size)
    return files


def converters():
    sys.path[:0] = [str(HERE/'tools'/d) for d in ('guests','heihachi','spawn')]
    import setup_guests
    return setup_guests


def source_guests(args):
    mod = converters()
    spawn = mod.releases.identify(mod.xiso.open_source(str(args.spawn))) if args.spawn else None
    hei = mod.ps2iso.identify_release(ps2_files(args.heihachi)) if args.heihachi else None
    return mod, spawn, hei


def guest_inventory(path):
    import build_guests
    m = json.loads((path/'guests.json').read_text(encoding='utf-8'))
    archive = path/'root-guests.olk'
    require(m.get('format') == 2 and m.get('disc') == 'GRSEAF' and
            m.get('gc_root_sha1') == build_guests.GRSEAF_ROOT_SHA1, 'Guest manifest does not match the US GameCube base')
    require(archive.is_file() and archive.stat().st_size == m['size'], 'Missing or incomplete root-guests.olk')
    with archive.open('rb') as stream:
        require(hashlib.file_digest(stream,'sha1').hexdigest() == m['sha1'], 'Guest archive checksum differs from its manifest')
    rows = m.get('guests')
    ids = [g['id'] for g in rows]
    require(ids in ([28],[29],[29,28]) and all(g['block'] == 982+i*39 for i,g in enumerate(rows)), 'Unexpected guest roster layout')
    return m


def summary(game):
    report = {'game': str(game), 'disc':'GRSEAF', 'stock_files':len(BASE),
              'stock_bytes':sum(info['bytes'] for info in BASE.values()), 'guest_ids':[],'guest_bytes':0}
    if (game/'guests').exists():
        converters()
        data = guest_inventory(game/'guests')
        report['guest_ids'] = [r['id'] for r in data['guests']]
        report['guest_bytes'] = data['size'] + (game/'guests/guests.json').stat().st_size
        report['guest_archive_sha1'] = data['sha1']
    return report


def prepare(args):
    source = args.gamecube.resolve()
    target = args.output.resolve()/'game'
    require(source != target and not (source.is_dir() and target.is_relative_to(source)),
            'Choose a separate output folder to preserve the input GameCube extraction.')
    if args.cc:
        os.environ['CC'] = str(args.cc)
    want_guests = bool(args.spawn or args.heihachi)
    if want_guests:
        mod, spawn, hei = source_guests(args)
    existing = target.exists()
    if existing:
        require(target.is_dir() and not target.is_symlink(), f'Output game folder is unavailable: {target}')
        process_base(source)
        process_base(target)
        if not want_guests:
            return summary(target)
        if (target/'guests').exists():
            m = guest_inventory(target/'guests')
            actual = {g['id']:g['source'] for g in m['guests']}
            require(actual == mod._sources(spawn,hei) and m.get('converter') == mod.build_guests._converter_version(),
                    'This output already has a different guest selection. Choose a new output folder and give every desired donor.')
            return summary(target)

    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ringout-data-',dir=target.parent) as temp:
        stage = Path(temp).resolve()
        require(stage.parent == target.parent, 'Private staging directory is outside the chosen output')
        game = target if existing else stage/'game'
        if not existing:
            process_base(source,game)
        if want_guests:
            guest_stage=stage/'guests'
            guest_stage.mkdir()
            # The PS5 roster needs the data pair. The desktop setup's optional
            # intro copier invokes an external movie decoder unavailable on PS5.
            mod.build(str(guest_stage),str(game),spawn,hei)
            m = guest_inventory(guest_stage)
            expected = mod._sources(spawn,hei)
            require({g['id']:g['source'] for g in m['guests']}==expected, 'Converted donor provenance differs')
            require(not (game/'guests').exists(), 'Guest destination changed during preparation')
            guest_stage.rename(game/'guests')
        if not existing:
            require(not target.exists(), 'Output game folder changed during preparation')
            game.rename(target)
    return summary(target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='mode',required=True)
    p=commands.add_parser('prepare',help='create the game/ folder under the chosen PC output directory')
    p.add_argument('gamecube',type=Path,help='plain US ISO/GCM or an extracted game folder with files/ and sys/')
    p.add_argument('--output',type=Path,required=True,help='PC output parent for game/')
    p.add_argument('--spawn',type=Path,help='Xbox ISO/XISO or extracted disc folder')
    p.add_argument('--heihachi',type=Path,help='US PS2 ISO or folder with ROOT.OLK and SLUS_206.43')
    p.add_argument('--cc',help='C compiler executable for guest audio, e.g. a path to zig.exe')
    p=commands.add_parser('check',help='verify an existing game folder in place')
    p.add_argument('game',type=Path)
    args=parser.parse_args()
    try:
        if args.mode=='check':
            game=args.game.resolve()
            require(game.is_dir(),'Supply the game folder containing files/ and sys/.')
            process_base(game)
            report=summary(game)
        else:
            report=prepare(args)
    except Exception as error:
        print('RingOut data preparation stopped:',error,file=sys.stderr)
        return 1
    print(json.dumps(report,indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
