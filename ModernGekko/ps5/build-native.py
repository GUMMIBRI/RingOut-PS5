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
parser.add_argument('--host-build', help='fresh source-matched CMake host build, with BUILD-ATTESTATION.json')
parser.add_argument('--include-ps5-menu', action='store_true',
                    help='rebuild the PS5 host loop with the menu lifecycle integration')
parser.add_argument('--trace-boot', action='store_true', help='rebuild Dolphin boot phase tracers')
parser.add_argument('--use-title-heap', action='store_true', help='use PS5 platform direct-memory title heap')
args = parser.parse_args()
if not args.build_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in args.build_id):
    parser.error('--build-id must contain only letters, digits, dash, dot or underscore')
workspace = Path(__file__).resolve().parents[3]
source = Path(__file__).resolve().parent
source_root = source.parents[1]
revision = subprocess.run(['git', '-C', str(source_root), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True)
if revision.returncode:
    parser.error('cannot identify source revision')
work = workspace / 'aot-work/ps5-aot-grseaf-r1'
host_build = Path(args.host_build).resolve() if args.host_build else work / 'host-build-sdk'
if args.host_build:
    attestation_path = host_build / 'BUILD-ATTESTATION.json'
    if not attestation_path.is_file():
        parser.error('fresh host build requires BUILD-ATTESTATION.json')
    attestation = json.loads(attestation_path.read_text())
    if (attestation.get('status') != 'success' or
        attestation.get('source_revision') != revision.stdout.strip() or
        Path(attestation.get('source_root', '')).resolve() != source_root.resolve() or
        hashlib.sha256((host_build / 'build.ninja').read_bytes()).hexdigest() != attestation.get('build_ninja_sha256')):
        parser.error('host build attestation does not match source and CMake build')
    dirty = subprocess.run(['git', '-C', str(source_root), 'status', '--porcelain', '--untracked-files=no'],
                           capture_output=True, text=True)
    if dirty.returncode or dirty.stdout.strip():
        parser.error('fresh host build requires a clean tracked source checkout')
    archives = attestation.get('archives', {})
    if not archives:
        parser.error('fresh host build attestation has no archive hashes')
    for relative, expected in archives.items():
        path = (host_build / relative).resolve()
        if not path.is_relative_to(host_build) or not path.is_file():
            parser.error('fresh host build archive mismatch: ' + relative)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                parser.error('fresh host build archive mismatch: ' + relative)
else:
    if source != (workspace / 'source/ModernGekko/ps5').resolve():
        parser.error('this pinned recipe uses a different source checkout and old host archives; configure and rebuild for this checkout first')
    if revision.stdout.strip() != '9339899231d9cf90282c7b4c17eb1cf0c3c4e14c':
        parser.error('host archives are pinned to the older source revision; rebuild them before producing a candidate')
# Preserve a mapped drive: the pinned converter cannot write UNC output paths.
stage = Path(args.stage).absolute()
if str(stage).startswith('\\\\'):
    parser.error('use a local or mapped-drive stage path, not UNC')
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
if args.include_ps5_menu:
    item = source / 'platform.cpp'
    inputs.append(record(item))
    target = 'CMakeFiles/moderngekko.dir/ps5/platform.cpp.o'
    compile_args = windows_argv(run([ninja, '-t', 'commands', target], host_build).strip().splitlines()[-1])
    assert Path(compile_args[0]) == llvm / 'clang++.exe'
    assert Path(compile_args[compile_args.index('-c') + 1]) == item
    output = stage / 'ps5_platform.o'
    for flag, value in [('-o', output), ('-MF', stage / 'platform.cpp.d'), ('-MT', output)]:
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
if args.include_ps5_menu:
    # LLVM's Windows archive replacement compares member names without case.
    # Platform.cpp.o and platform.cpp.o coexist; rename only the exact PS5
    # member in the staged copy before removing it, preserving Dolphin's one.
    data = bytearray(runtime_archive.read_bytes())
    offset = 8
    found = 0
    while offset < len(data):
        header = data[offset:offset + 60]
        size = int(header[48:58])
        if header[:16].rstrip() == b'platform.cpp.o/':
            data[offset:offset + 16] = b'ps5_old.cpp.o/  '
            found += 1
        offset += 60 + size + (size % 2)
    assert offset == len(data) and found == 1
    runtime_archive.write_bytes(data)
    run([llvm / 'llvm-ar.exe', 'd', runtime_archive, 'ps5_old.cpp.o'])
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

# Optional bounded diagnostic: preserve host archives, replace only named boot
# members in staged copies, and retain the exact Ninja commands and inputs.
boot_archives = {}
if args.trace_boot:
    for library, members_spec in [
        ('Core', [('Boot/BootParameters.cpp', 'BootParameters.cpp'), ('Boot/BootManager.cpp', 'BootManager.cpp'), ('Core.cpp', 'Core.cpp')]),
        ('DiscIO', [('DirectoryBlob.cpp', 'DirectoryBlob.cpp')])]:
        libname = 'libcore.a' if library == 'Core' else 'libdiscio.a'
        original = host_build / 'vendor/dolphin/Source/Core' / library / libname
        archive = stage / libname
        inputs.append(record(original))
        shutil.copyfile(original, archive)
        objects = []
        for relative, name in members_spec:
            item = source.parent / 'vendor/dolphin/Source/Core' / library / relative
            target = f'vendor/dolphin/Source/Core/{library}/CMakeFiles/{library.lower()}.dir/{relative}.o'
            inputs.append(record(item))
            argv = windows_argv(run([ninja, '-t', 'commands', target], host_build).strip().splitlines()[-1])
            assert Path(argv[0]) == llvm / 'clang++.exe' and Path(argv[argv.index('-c') + 1]) == item
            obj = stage / (name + '.o')
            for flag, value in [('-o', obj), ('-MF', stage / (name + '.d')), ('-MT', obj)]:
                argv[argv.index(flag) + 1] = str(value)
            argv[1:1] = ['-DRINGOUT_BOOT_TRACE=1', '-I', str(source)]
            run(argv, host_build)
            objects.append(obj)
        run([llvm / 'llvm-ar.exe', 'r', archive, *objects])
        archive_members = run([llvm / 'llvm-ar.exe', 't', archive]).splitlines()
        assert all(archive_members.count(obj.name) == 1 for obj in objects)
        boot_archives['vendor/dolphin/Source/Core/' + library + '/' + libname] = str(archive)

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
substitutions.update(boot_archives)
substitutions = {key.replace('\\', '/'): value for key, value in substitutions.items()}
link = [substitutions.get(x.replace('\\', '/'), x) for x in link]
assert Path(link[link.index('-o') + 1]) == stage / 'ringout-native.elf'
position = link.index(str(stage / 'main.cpp.o'))
link[position:position] = [str(stage / 'posix_filesystem.c.o')]
link[:0] = ['--defsym=' + name + '=ps5_' + name
            for name in ['fork', 'link', 'dup', 'symlink', 'readlink', 'pathconf', 'isatty']]
# RADV's WSI obtains this callback through a weak entrypoint table. Weak
# references do not extract the provider from the static archive; without it,
# wsi_device_init calls a null GetPhysicalDeviceProperties2 during startup.
link.insert(0, '--undefined=vk_common_GetPhysicalDeviceProperties2')
if args.use_title_heap:
    # Existing PS5 platform archive provides the same synchronized segmented
    # direct-memory allocator used by the working SC2 title. Keep the entire
    # allocation family consistent, including libc-allocated foreign pointers.
    link[:0] = ['--wrap=' + name for name in ['malloc', 'calloc', 'realloc', 'free',
               'posix_memalign', 'aligned_alloc', 'memalign', 'malloc_usable_size',
               'reallocf', 'reallocarray', 'getline', 'getdelim']]
(stage / 'link-args.json').write_text(json.dumps(link, indent=2))
for entry in link:
    path = Path(entry)
    if not path.is_absolute(): path = host_build / path
    if path.is_file() and path.suffix in ('.a', '.o', '.so', '.ld', '.map'):
        if args.host_build and path.suffix == '.a' and path.resolve().is_relative_to(host_build):
            if path.resolve().relative_to(host_build).as_posix() not in archives:
                raise RuntimeError('linked host archive is absent from attestation: ' + str(path))
        inputs.append(record(path))
run([llvm / 'ld.lld.exe', *link], host_build)
definitions = run([llvm / 'llvm-nm.exe', '--defined-only', stage / 'ringout-native.elf'])
assert any(line.split()[-1:] == ['vk_common_GetPhysicalDeviceProperties2']
           for line in definitions.splitlines()), 'RADV physical-device callback is missing'
if args.use_title_heap:
    for symbol in ['__wrap_malloc', '__wrap_free', 'ps5_heap_malloc', 'ps5_heap_owns']:
        assert any(line.split()[-1:] == [symbol] for line in definitions.splitlines()), f'missing heap symbol {symbol}'
run([converter, 'link', '--in', stage / 'ringout-native.elf', '--out', stage / 'eboot.elf',
     '--stub-dir', sdk / 'target/lib', '--file-name', 'eboot.elf'])
run([converter, 'self', '--sign', '--in', stage / 'eboot.elf', '--out', stage / 'eboot.bin'])
inspection = run([converter, 'self', '--inspect', '--file', stage / 'eboot.bin'])
(stage / 'self-inspect.txt').write_text(inspection)
revision = run(['git', '-C', source_root, 'rev-parse', 'HEAD']).strip()
receipt = {'build_id': args.build_id, 'source_revision': revision,
           'include_ps5_menu': args.include_ps5_menu,
           'trace_boot': args.trace_boot,
           'use_title_heap': args.use_title_heap,
           'source_state': 'working tree; exact linked source/input hashes below',
           'inputs': inputs, 'tools': [record(llvm / x) for x in ['clang.exe', 'clang++.exe', 'ld.lld.exe', 'llvm-ar.exe']],
           'converter': record(converter), 'input_elf': record(stage / 'ringout-native.elf'),
           'elf': record(stage / 'eboot.elf'), 'eboot': record(stage / 'eboot.bin'),
           'commands': record(stage / 'commands.json'), 'self_inspection': inspection,
           'installed': False, 'hardware_tested': False}
(stage / 'FINALIZATION.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({key: receipt[key] for key in ['build_id', 'elf', 'eboot']}))
