# SPDX-License-Identifier: GPL-2.0-or-later
"""Build, assemble and statically qualify one private RingOut candidate.

Never launches, transfers, or establishes gameplay. The stage must be new.
"""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, sys
here=pathlib.Path(__file__).resolve().parent
workspace=here.parents[2]
sdkroot=pathlib.Path('C:/.pe/ps5-native/gpu-platform-20261030')
parser=argparse.ArgumentParser()
parser.add_argument('--stage',required=True)
parser.add_argument('--build-id',required=True)
parser.add_argument('--host-build',help='fresh source-matched host build with attestation')
parser.add_argument('--rollback',required=True,help='previous complete staged candidate directory')
parser.add_argument('--include-ps5-menu',action='store_true')
parser.add_argument('--trace-boot',action='store_true')
parser.add_argument('--use-title-heap',action='store_true')
parser.add_argument('--dry-run',action='store_true')
args=parser.parse_args()
if not args.host_build and here != (workspace/'source/ModernGekko/ps5').resolve():
    parser.error('this pinned recipe uses a different source checkout and old host archives; configure and rebuild for this checkout first')
stage=pathlib.Path(args.stage).absolute()
rollback=pathlib.Path(args.rollback).absolute()
if str(stage).startswith('\\\\'):
    parser.error('use a local or mapped-drive stage, not UNC')
if not args.build_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in args.build_id):
    parser.error('invalid build ID')
if stage.exists() and any(stage.iterdir()):parser.error('stage must be new or empty')
for f in (rollback/'eboot.bin',rollback/'app/PPSA99875/sce_sys/param.json'):
    if not f.is_file():parser.error('rollback missing: '+str(f))
pwsh=shutil.which('pwsh')
if not pwsh:parser.error('PowerShell 7 is required')
llvm=sdkroot/'deps/llvm/bin'; sdk=sdkroot/'deps/ps5-payload-sdk'
plan=[
 [sys.executable,str(here/'build-native.py'),'--stage',str(stage),'--build-id',args.build_id]+(['--host-build',args.host_build] if args.host_build else [])+(['--include-ps5-menu'] if args.include_ps5_menu else [])+(['--trace-boot'] if args.trace_boot else [])+(['--use-title-heap'] if args.use_title_heap else []),
 [sys.executable,str(here/'prepare-native-package.py'),str(stage)],
 [pwsh,'-NoProfile','-File',str(sdkroot/'native-candidates/recipe/audit-application-imports.ps1'),'-Elf',str(stage/'ringout-native.elf'),'-StubDirectory',str(sdk/'target/lib'),'-ReadElf',str(llvm/'llvm-readelf.exe'),'-Output',str(stage/'imports-native.json')],
 [pwsh,'-NoProfile','-File',str(workspace/'aot-work/native-audit-tools/audit-application-runtime.ps1'),'-Elf',str(stage/'ringout-native.elf'),'-ImportAudit',str(stage/'imports-native.json'),'-LlvmBin',str(llvm),'-Output',str(stage/'runtime-native.json')],
 [sys.executable,str(here/'qualify-native-package.py'),str(stage),str(rollback)] ]
if args.dry_run:
 print(json.dumps({'stage':str(stage),'rollback':str(rollback),'plan':plan},indent=2));sys.exit(0)
# Keep compiler temporary files on the selected volume; no pre-existing path is reused.
tmp=stage.parent/(stage.name+'-temp')
if tmp.exists():parser.error('temporary directory already exists: '+str(tmp))
tmp.mkdir(parents=True); env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),PYTHONDONTWRITEBYTECODE='1')
records=[]
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
inputs=[here/x for x in ('build-package.py','build-native.py','prepare-native-package.py','qualify-native-package.py')]
inputs += [sdkroot/'native-candidates/recipe/audit-application-imports.ps1',
           workspace/'aot-work/native-audit-tools/audit-application-runtime.ps1',
           workspace/'aot-work/native-audit-tools/scan-inline-syscalls.py',
           workspace/'aot-work/FIRST-BOOT-R1-COMPLETE-MANIFEST.json',
           pathlib.Path('C:/SC2/tools/ps5_finalize_payload.py'),
           pathlib.Path('C:/Users/gumbreezy/.codex/skills/ps5-build-package/scripts/check_package.py'),
           pathlib.Path('C:/Users/gumbreezy/.codex/skills/ps5-build-package/scripts/brand_channel.py'),
           llvm/'llvm-readelf.exe',llvm/'llvm-nm.exe',llvm/'llvm-objdump.exe',
           rollback/'eboot.bin',rollback/'app/PPSA99875/sce_sys/param.json']
initial={str(p):digest(p) for p in inputs}
for command in plan:
 r=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True)
 records.append({'argv':command,'cwd':str(workspace),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 if stage.exists():
  (stage/'PACKAGE-COMMANDS.json').write_text(json.dumps({'input_hashes_before':initial,'commands':records},indent=2))
 if r.returncode:
  sys.stderr.write(r.stderr or r.stdout)
  raise SystemExit(r.returncode)
if any(digest(p)!=initial[str(p)] for p in inputs):raise SystemExit('recipe source changed during build')
print(json.dumps({'stage':str(stage),'status':'STATIC_PACKAGE_PASS','installed':False,'hardware_tested':False}))
