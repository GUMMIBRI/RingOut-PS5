import argparse, hashlib, importlib.util, json, os, pathlib, subprocess, shutil, sys
from guest_package import guest_files
parser=argparse.ArgumentParser()
parser.add_argument('stage')
parser.add_argument('--guest-dir')
args=parser.parse_args()
root = pathlib.Path(args.stage).absolute()
workspace = pathlib.Path(__file__).resolve().parents[3]
app = root / 'app/PPSA99875'
app.mkdir(parents=True, exist_ok=True)
def sha(p):
    with pathlib.Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def art(p): return {'path': str(p), 'sha256': sha(p)}
baseline = json.loads((workspace / 'aot-work/FIRST-BOOT-R1-COMPLETE-MANIFEST.json').read_text())
inventory=[]
for item in baseline['files']:
    relative=pathlib.PurePosixPath(item['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    if item['path'] in ['eboot.bin', 'sce_sys/param.json', 'README.txt']: continue
    destination=app / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Hard links retain the full immutable private content without a second 1.4 GB copy.
    # Never edit these links or use this private development folder as a public release.
    if not destination.exists(): shutil.copyfile(item['source'], destination)
    assert sha(destination)==item['sha256'], item['path']
    inventory.append({**art(destination), 'bytes':destination.stat().st_size})
eboot=app/'eboot.bin'
if not eboot.exists(): os.link(root/'eboot.bin',eboot)
param=app/'sce_sys/param.json'
original=workspace/'aot-work/first-boot-r1/sce_sys/param.json'
branding=pathlib.Path('C:/Users/gumbreezy/.codex/skills/ps5-build-package/scripts/brand_channel.py')
if not param.exists(): subprocess.run(['python', str(branding), str(original),str(param),'--channel','dev'],check=True)
(app/'user').mkdir(exist_ok=True)
readme=app/'README.txt'
readme.write_text('RingOut (dev), development, private local test candidate.\n'
    'Contains owner-supplied GameCube disc data and a private runtime companion. Do not redistribute.\n'
    'App folder contract: /mnt/usb0/homebrew/PPSA99875. Preserve existing user saves/settings.\n'
    'Startup logs: startup-0.log through startup-5.log beside eboot.bin, bounded to 64 KiB each.\n'
    'Absolute launch executable paths and absolute game/user arguments are supported; early logs use USB0.\n'
    'Expected test: normal launcher entry, observe startup then real game title/select. No autonomous launch.\n'
    'Boot, shell exit and relaunch unverified. Xbox/PS2 guest integration remains separate.\n'
    'POSIX subprocess/symlink/hardlink operations report ENOSYS. pathconf uses kernel descriptor query.\n'
    'Private baseline copies; do not redistribute.\n')
inventory.extend([{**art(p), 'bytes':p.stat().st_size} for p in [eboot,param,readme]])
if args.guest_dir:
    guest=pathlib.Path(args.guest_dir).resolve()
    sources=guest_files(guest,app/'game/files/root.olk')
    target=app/'game/guests'; target.mkdir(parents=True,exist_ok=False)
    for src in sources:
        dst=target/src.name
        try: os.link(src,dst)
        except OSError: shutil.copyfile(src,dst)
        if sha(src)!=sha(dst):raise ValueError('guest file changed during packaging: '+src.name)
        inventory.append({**art(dst),'bytes':dst.stat().st_size})
    readme.write_text(readme.read_text()+'Private guest archive included; both source games remain required for local preparation.\n')
    inventory=[{**art(p),'bytes':p.stat().st_size} if p==readme else item
               for item in inventory for p in [pathlib.Path(item['path'])]]
(root/'CONTENT.json').write_text(json.dumps({'app_root':str(app),'all_hashes_verified':True,
    'private':True,'copied_immutable_assets':True,'guest_source':str(guest) if args.guest_dir else None,
    'files':inventory},indent=2))
print('assembled',len(inventory),'files')
finalizer=pathlib.Path('C:/SC2/tools/ps5_finalize_payload.py')
spec=importlib.util.spec_from_file_location('finalizer',finalizer)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original_elf=module.preflight(root/'ringout-native.elf',pathlib.Path('C:/.pe/ps5-native/gpu-platform-20261030/deps/llvm/bin/llvm-nm.exe'))
retained=module.retained(original_elf,root/'eboot.elf')
(root/'layout.json').write_text(json.dumps({'script':art(finalizer),'input_elf':art(root/'ringout-native.elf'),
    'elf':art(root/'eboot.elf'),'preflight_passed':True,'retained_passed':True,'retained_sections':retained},indent=2))
print('layout/retention passed',len(retained),'sections')


