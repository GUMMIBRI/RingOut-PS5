"""Pinned local native recipe. Reuses the recorded GRSEAF/Dolphin archives.

Does not transfer, launch, or claim a hardware-tested build. Source revisions,
commands, tool hashes, inputs and ELF/SELF pairing are retained with each run.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--stage', required=True)
parser.add_argument('--build-id', required=True)
args = parser.parse_args()
if not args.build_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in args.build_id):
    parser.error('--build-id must contain only letters, digits, dash, dot or underscore')
workspace = Path(__file__).resolve().parents[3]
source = workspace / 'source/ModernGekko/ps5'
work = workspace / 'aot-work/ps5-aot-grseaf-r1'
stage = Path(args.stage).resolve()
if stage.exists() and any(stage.iterdir()):
    parser.error('--stage must be new or empty; finalized candidates are immutable')
stage.mkdir(parents=True, exist_ok=True)
platform = Path('C:/.pe/ps5-native/gpu-platform-20261030')
sdk = platform / 'deps/ps5-payload-sdk'
llvm = platform / 'deps/llvm/bin'
converter = platform / 'native-candidates/tool/ps5-native-tool.exe'
commands = []
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def record(path):
    return {'path': str(path), 'sha256': sha(path), 'bytes': Path(path).stat().st_size}
def run(argv, cwd=stage):
    argv = [str(x) for x in argv]
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    commands.append({'argv': argv, 'cwd': str(cwd), 'exit_code': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr})
    (stage / 'commands.json').write_text(json.dumps(commands, indent=2))
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout

common = ['--target=x86_64-unknown-freebsd12', '-isysroot', sdk,
          '-isystem', sdk / 'target/include', '-isystem', sdk / 'target/include_common',
          '-fPIC', '-O2', '-femulated-tls', '-fno-stack-protector', '-Wall', '-Wextra', '-Werror',
          '-DRINGOUT_BUILD_ID="' + args.build_id + '"']
cpp = ['-nostdinc++', '-isystem', sdk / 'target/include/c++/v1', '-std=gnu++23',
       '-fexperimental-library', '-I', source.parent / 'include']
inputs = []
for name in ['app_crt.cpp', 'main.cpp', 'native_startup_log.c', 'posix_filesystem.c']:
    item = source / name
    inputs.append(record(item))
    flags = cpp + common if item.suffix == '.cpp' else common
    if name == 'native_startup_log.c': flags = flags + ['-fno-builtin']
    run([llvm / ('clang++.exe' if item.suffix == '.cpp' else 'clang.exe'),
         *flags, '-c', item, '-o', stage / (name + '.o')])
for name in ['native_startup.h', 'startup_log.h', 'build-native.py']:
    inputs.append(record(source / name))

# Rebuild the changed runtime members with their exact existing CMake recipe.
# Work on a staged archive so frozen candidates and the original host build
# remain reproducible. Recompiling only ps5/main.cpp misses game.cpp fixes.
host_build = work / 'host-build-sdk'
ninja = sdk / 'win/ninja.exe'
def windows_argv(command):
    shell32 = ctypes.WinDLL('shell32', use_last_error=True)
    split = shell32.CommandLineToArgvW
    split.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    split.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    result = split(command, ctypes.byref(count))
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [result[i] for i in range(count.value)]
    finally:
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(result)

runtime_objects = []
for name in ['game.cpp', 'dolphin_runtime.cpp']:
    item = source.parent / 'src/runtime' / name
    inputs.append(record(item))
    target = 'CMakeFiles/moderngekko.dir/src/runtime/' + name + '.o'
    command = run([ninja, '-t', 'commands', target], host_build).strip().splitlines()[-1]
    compile_args = windows_argv(command)
    assert Path(compile_args[0]) == llvm / 'clang++.exe'
    assert Path(compile_args[compile_args.index('-c') + 1]) == item
    output = stage / (name + '.o')
    for flag, value in [('-o', output), ('-MF', stage / (name + '.d')), ('-MT', output)]:
        compile_args[compile_args.index(flag) + 1] = str(value)
    run(compile_args, host_build)
    runtime_objects.append(output)
original_archive = host_build / 'libmoderngekko.a'
with original_archive.open('rb') as stream:
    assert stream.read(8) == b'!<arch>\n', 'thin archives require explicit member relocation'
inputs.append(record(original_archive))
for item in [host_build / 'build.ninja', host_build / 'CMakeFiles/rules.ninja', ninja]:
    inputs.append(record(item))
runtime_archive = stage / 'libmoderngekko.a'
shutil.copyfile(original_archive, runtime_archive)
run([llvm / 'llvm-ar.exe', 'r', runtime_archive, *runtime_objects])
members = run([llvm / 'llvm-ar.exe', 't', runtime_archive]).splitlines()
for item in runtime_objects:
    assert members.count(item.name) == 1, 'runtime replacement must occur exactly once'

# Keep diagnostics in the real UI initialization path; use a dedicated trace
# macro so replaying this object does not change Dolphin platform/ABI defines.
ui_source = source.parent / 'vendor/dolphin/Source/Core/UICommon/UICommon.cpp'
ui_target = 'vendor/dolphin/Source/Core/UICommon/CMakeFiles/uicommon.dir/UICommon.cpp.o'
inputs.append(record(ui_source))
ui_args = windows_argv(run([ninja, '-t', 'commands', ui_target], host_build).strip().splitlines()[-1])
assert Path(ui_args[0]) == llvm / 'clang++.exe'
assert Path(ui_args[ui_args.index('-c') + 1]) == ui_source
ui_object = stage / 'UICommon.cpp.o'
for flag, value in [('-o', ui_object), ('-MF', stage / 'UICommon.cpp.d'), ('-MT', ui_object)]:
    ui_args[ui_args.index(flag) + 1] = str(value)
ui_args[1:1] = ['-DRINGOUT_NATIVE_INIT_TRACE=1', '-I', str(source)]
run(ui_args, host_build)
original_ui_archive = host_build / 'vendor/dolphin/Source/Core/UICommon/libuicommon.a'
with original_ui_archive.open('rb') as stream:
    assert stream.read(8) == b'!<arch>\n'
inputs.append(record(original_ui_archive))
ui_archive = stage / 'libuicommon.a'
shutil.copyfile(original_ui_archive, ui_archive)
run([llvm / 'llvm-ar.exe', 'r', ui_archive, ui_object])
assert run([llvm / 'llvm-ar.exe', 't', ui_archive]).splitlines().count(ui_object.name) == 1

fp = work / 'staged-native-r3/fp.o'
inputs.append(record(fp))
link = json.loads((work / 'staged-native-r3/link-args.json').read_text())
substitutions = {
    str(work / 'staged-native-r3/app_crt.o'): str(stage / 'app_crt.cpp.o'),
    'CMakeFiles/ringout_ps5.dir/ps5/main.cpp.o': str(stage / 'main.cpp.o'),
    'CMakeFiles/ringout_ps5.dir/ps5/startup_log.c.o': str(stage / 'native_startup_log.c.o'),
    'libmoderngekko.a': str(runtime_archive),
    'vendor/dolphin/Source/Core/UICommon/libuicommon.a': str(ui_archive),
    str(work / 'staged-native-r3/ringout-native-r3.elf'): str(stage / 'ringout-native.elf')}
substitutions = {key.replace('\\', '/'): value for key, value in substitutions.items()}
link = [substitutions.get(x.replace('\\', '/'), x) for x in link]
assert Path(link[link.index('-o') + 1]) == stage / 'ringout-native.elf'
position = link.index(str(stage / 'main.cpp.o'))
link[position:position] = [str(stage / 'posix_filesystem.c.o')]
link[:0] = ['--defsym=' + name + '=ps5_' + name
            for name in ['fork', 'link', 'dup', 'symlink', 'readlink', 'pathconf', 'isatty']]
(stage / 'link-args.json').write_text(json.dumps(link, indent=2))
for entry in link:
    path = Path(entry)
    if not path.is_absolute(): path = work / 'host-build-sdk' / path
    if path.is_file() and path.suffix in ('.a', '.o', '.so', '.ld', '.map'):
        inputs.append(record(path))
run([llvm / 'ld.lld.exe', *link], work / 'host-build-sdk')
run([converter, 'link', '--in', stage / 'ringout-native.elf', '--out', stage / 'eboot.elf',
     '--stub-dir', sdk / 'target/lib', '--file-name', 'eboot.elf'])
run([converter, 'self', '--sign', '--in', stage / 'eboot.elf', '--out', stage / 'eboot.bin'])
inspection = run([converter, 'self', '--inspect', '--file', stage / 'eboot.bin'])
(stage / 'self-inspect.txt').write_text(inspection)
revision = run(['git', '-C', workspace / 'source', 'rev-parse', 'HEAD']).strip()
receipt = {'build_id': args.build_id, 'source_revision': revision,
           'source_state': 'working tree; exact linked source/input hashes below',
           'inputs': inputs, 'tools': [record(llvm / x) for x in ['clang.exe', 'clang++.exe', 'ld.lld.exe', 'llvm-ar.exe']],
           'converter': record(converter), 'input_elf': record(stage / 'ringout-native.elf'),
           'elf': record(stage / 'eboot.elf'), 'eboot': record(stage / 'eboot.bin'),
           'commands': record(stage / 'commands.json'), 'self_inspection': inspection,
           'installed': False, 'hardware_tested': False}
(stage / 'FINALIZATION.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({key: receipt[key] for key in ['build_id', 'elf', 'eboot']}))
