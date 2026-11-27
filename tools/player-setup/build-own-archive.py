"""Build a player-private GRSEAF AOT archive using supplied public tools.
SPDX-License-Identifier: GPL-2.0-or-later
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def validate(args):
    paths = [args.input / 'main.dol', args.input / 'PREPARE.json', args.dolrecomp,
             args.llvm / 'clang.exe', args.llvm / 'llvm-ar.exe', args.llvm / 'llvm-ranlib.exe',
             args.llvm / 'llvm-nm.exe', args.cmake, args.ninja,
             args.sdk / 'target/include/stdlib.h',
             args.source / 'dist/RingOut-1.0-dist/module-src/CMakeLists.txt']
    missing = [str(p) for p in paths if not p.is_file()]
    if missing: raise ValueError('Missing required player/tool/source input: ' + ', '.join(missing))
    info = json.loads((args.input / 'PREPARE.json').read_text())
    if info.get('game_id') != 'GRSEAF' or info.get('dol_sha256') != sha(args.input / 'main.dol'):
        raise ValueError('Prepared GRSEAF program does not match its preparation receipt.')
    if args.out.exists(): raise ValueError('Output directory already exists; choose a new private build directory.')
    if not 1 <= args.jobs <= 16: raise ValueError('Use between one and sixteen compiler jobs.')
    return paths, info

def build(args):
    paths, info = validate(args)
    args.out.mkdir(parents=True)
    commands = []
    def run(argv, label):
        argv = list(map(str, argv)); commands.append(dict(label=label, argv=argv))
        with (args.out / (label + '.log')).open('w') as log:
            result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
        commands[-1]['exit'] = result.returncode
        (args.out / 'COMMANDS.json').write_text(json.dumps(commands, indent=2))
        if result.returncode: raise RuntimeError(label + ' failed; inspect its local log.')
    recipe = json.loads((Path(__file__).parent / 'grseaf-ps5-recipe.json').read_text())
    work = args.out / 'generated-program'
    replacements = {'$DOL': str(args.input / 'main.dol'), '$SOURCE': str(args.source),
                    '$WORK': str(work), '$JOBS': '-j' + str(args.jobs)}
    argv = recipe['arguments']
    for old, new in replacements.items(): argv = [s.replace(old, new) for s in argv]
    run([args.dolrecomp, *argv], 'generate')
    generated = work / 'generated'
    shutil.copyfile(args.input / 'main.dol', generated / 'main.dol')
    header = (generated / 'generated.h').read_text()
    if '#define DOLRECOMP_GATE_GROUPS 0x6u' not in header:
        raise RuntimeError('Generated guest gates do not advertise the required mask 0x6.')
    mod = args.source / 'dist/RingOut-1.0-dist/module-src'
    deps = mod / 'deps'; output = args.out / 'module'
    # Existing verified target recipe. Paths are arguments, never shell text.
    cflags = '-isystem "' + str(args.sdk / 'target/include') + '" -isystem "' + str(args.sdk / 'target/include_common') + '" -march=znver2 -fPIC'
    run([args.cmake, '-S', mod, '-B', output, '-G', 'Ninja',
         '-DCMAKE_MAKE_PROGRAM=' + str(args.ninja), '-DCMAKE_SYSTEM_NAME=FreeBSD',
         '-DCMAKE_SYSTEM_PROCESSOR=x86_64', '-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY',
         '-DCMAKE_C_COMPILER=' + str(args.llvm / 'clang.exe'),
         '-DCMAKE_C_COMPILER_TARGET=x86_64-unknown-freebsd12.0',
         '-DCMAKE_C_FLAGS=' + cflags, '-DCMAKE_AR=' + str(args.llvm / 'llvm-ar.exe'),
         '-DCMAKE_RANLIB=' + str(args.llvm / 'llvm-ranlib.exe'), '-DGAME_ID=GRSEAF',
         '-DGENERATED_DIR=' + str(generated), '-DMODULE_STATIC=ON', '-DMODULE_LTO=OFF',
         '-DMODULE_PSQ_FAST=ON', '-DMODULE_MEM_FAST=ON',
         '-DDOLRECOMP_SRC=' + str(deps / 'dolrecomp-src'),
         '-DGXRUNTIME_INC=' + str(deps / 'gxruntime-include'),
         '-DCHASSIS_ABI_DIR=' + str(deps / 'chassis-abi'),
         '-DMODULE_TEMPLATE=' + str(deps / 'module-template')], 'configure')
    run([args.cmake, '--build', output, '--parallel', str(args.jobs)], 'compile')
    archive = output / 'gGRSEAF_recomp.a'
    nm = subprocess.run([str(args.llvm / 'llvm-nm.exe'), '--defined-only', str(archive)],
                        text=True, capture_output=True, check=True)
    (args.out / 'DEFINED-SYMBOLS.txt').write_text(nm.stdout)
    required = ['staticrecomp_get_module', 'staticrecomp_gate_groups', 'dolrecomp_gate_armed', 'dolrecomp_gate_bypass']
    defined = {line.split()[-1] for line in nm.stdout.splitlines() if len(line.split()) >= 3}
    if not set(required) <= defined: raise RuntimeError('Compiled archive lacks required module/gate exports.')
    kit_revision = args.source / 'RINGOUT-SOURCE-REVISION.txt'
    revision = (kit_revision.read_text(encoding='ascii').strip() if kit_revision.is_file() else
                subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'],
                                        text=True).strip())
    receipt = dict(status='player-private-PS5-AOT-archive-built', source_revision=revision,
                   game_id='GRSEAF', program_sha256=info['dol_sha256'], gate_mask='0x6',
                   archive=str(archive), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
                   required_defined_symbols=required, inputs={str(p): sha(p) for p in paths},
                   generated_header_sha256=sha(generated / 'generated.h'),
                   original_game_content=True, redistribute=False,
                   pending=['player PRX finalization', 'installation'])
    (args.out / 'ARCHIVE-RECEIPT.json').write_text(json.dumps(receipt, indent=2))
    return receipt

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['input', 'source', 'dolrecomp', 'llvm', 'sdk', 'cmake', 'ninja', 'out']:
        p.add_argument('--' + name, required=True, type=lambda s: Path(s).resolve())
    p.add_argument('--jobs', type=int, default=4)
    a = p.parse_args()
    try: result = build(a)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e: p.exit(2, str(e) + '\n')
    print(json.dumps(result, indent=2))
if __name__ == '__main__': main()
