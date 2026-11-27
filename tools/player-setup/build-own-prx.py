"""Build the native PRX for a player's prepared AOT archive.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PRX_NAME = 'gGRSEAF_recomp.prx'
LOADER_HEADER_SHA256 = '1fe4edc33ad0f029bd828c09c76fbc5c8628204a8434480d04c419f9f76d5e61'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(args):
    receipt = json.loads((args.archive_dir / 'ARCHIVE-RECEIPT.json').read_bytes())
    archive = args.archive_dir / 'module/gGRSEAF_recomp.a'
    digest = sha256(archive)
    if (receipt.get('status') != 'player-private-PS5-AOT-archive-built' or
            receipt.get('game_id') != 'GRSEAF' or receipt.get('gate_mask') != '0x6' or
            receipt.get('archive_sha256') != digest or
            receipt.get('archive_bytes') != archive.stat().st_size):
        raise ValueError('The AOT archive differs from its original player preparation receipt.')
    if sha256(args.foundation / 'modules/prx_loader.h') != LOADER_HEADER_SHA256:
        raise ValueError('Use the matching PRX descriptor header from the reviewed foundation.')

    args.output.mkdir()
    descriptor = args.output / 'descriptor.o'
    shared = args.output / 'module.shared.elf'
    converted = args.output / 'module.elf'
    output = args.output / PRX_NAME
    stubs = args.sdk / 'target/lib'
    with (args.output / 'build.log').open('w', encoding='utf-8') as log:
        def run(command):
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)

        run([args.llvm / 'clang.exe', '--target=x86_64-unknown-freebsd12', '-std=c11', '-O2',
             '-Wall', '-Wextra', '-Werror', '-fPIC', '-ffunction-sections', '-fdata-sections',
             '-isystem', args.sdk / 'target/include', '-isystem', args.sdk / 'target/include_common',
             '-I', args.foundation / 'modules', '-I', args.source / 'ModernGekko/include',
             '-c', HERE / 'prx-game-descriptor.c', '-o', descriptor])
        run([args.llvm / 'ld.lld.exe', '--shared', '-Bsymbolic', '-T',
             args.foundation / 'tooling/native/ps5-pie.ld', '--eh-frame-hdr', '--version-script',
             HERE / 'prx-game-exports.map', '-z', 'max-page-size=0x4000', '-z', 'defs',
             '-soname', PRX_NAME, '-o', shared, descriptor, '--whole-archive', archive,
             '--no-whole-archive', '--as-needed', stubs / 'libSceLibcInternal.so',
             stubs / 'libkernel.so'])
        run([args.converter, 'link', '--module', '--in', shared, '--out', converted,
             '--stub-dir', stubs, '--module-sdk', '0x02000009', '--companion-sdk', '0x08050001',
             '--file-name', PRX_NAME])
        candidate = args.output / (PRX_NAME + '.pending')
        run([args.converter, 'self', '--sign', '--in', converted, '--out', candidate])
        run([args.converter, 'self', '--inspect', '--file', candidate])
        if sha256(archive) != digest:
            raise ValueError('The player archive changed while linking.')
        candidate.rename(output)
    facts = {'game_id': 'GRSEAF', 'archive_sha256': digest, 'native_elf_sha256': sha256(converted),
             'module_sha256': sha256(output), 'module_bytes': output.stat().st_size,
             'redistribute': False, 'title_loading_verified': False}
    (args.output / 'PRX-RECEIPT.json').write_text(json.dumps(facts, indent=2) + '\n', encoding='utf-8')
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ('archive-dir', 'source', 'foundation', 'sdk', 'llvm', 'converter', 'output'):
        parser.add_argument('--' + name, type=lambda value: Path(value).resolve(), required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
