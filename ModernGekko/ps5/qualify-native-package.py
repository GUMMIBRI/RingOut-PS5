"""Reconcile actual finalization, current hashes and raw local audits, then preflight."""
import hashlib,json,pathlib,shutil,subprocess,sys
root=pathlib.Path(sys.argv[1]).absolute()
app=root/'app/PPSA99875'
workspace=pathlib.Path(__file__).resolve().parents[3]
def sha(p):
    with pathlib.Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def art(p): return {'path':str(p),'sha256':sha(p)}
def read(name): return json.loads((root/name).read_text(encoding='utf-8-sig'))
receipt=read('FINALIZATION.json'); imports=read('imports-native.json'); runtime=read('runtime-native.json'); layout=read('layout.json')
native=sha(root/'ringout-native.elf'); elf=sha(root/'eboot.elf'); eboot=sha(root/'eboot.bin')
assert native==receipt['input_elf']['sha256']==imports['SHA256'].lower()==runtime['SHA256'].lower()
assert elf==receipt['elf']['sha256']==layout['elf']['sha256'] and native==layout['input_elf']['sha256']
assert eboot==receipt['eboot']['sha256']==sha(app/'eboot.bin')
assert runtime['Passed'] and not runtime['InlineSyscalls']
assert layout['preflight_passed'] and layout['retained_passed']
assert 'integrity: valid' in receipt['self_inspection']
assert sha(root/'commands.json')==receipt['commands']['sha256']
commands=read('commands.json'); assert all(x['exit_code']==0 for x in commands)
assert any('link' in x['argv'] and str(root/'eboot.elf') in x['argv'] for x in commands)
assert imports['ImportCount']==len(imports['Imports']) and imports['ImportCount']>0
snapshot=root/'source-snapshot';snapshot.mkdir(exist_ok=True)
for item in receipt['inputs']:
    path=pathlib.Path(item['path'])
    if path.suffix not in ['.c','.cpp','.h','.py']:continue
    assert sha(path)==item['sha256']
    shutil.copy2(path,snapshot/path.name)
audit={'elf':art(root/'eboot.elf'),'eboot':art(root/'eboot.bin'),'input_elf':art(root/'ringout-native.elf'),
       'imports_passed':True,'runtime_layout_passed':True,'self_integrity_passed':True,
       'raw_reports':[art(root/p) for p in ['imports-native.json','runtime-native.json','layout.json','FINALIZATION.json','commands.json']],
       'scope':'Native named imports mapped by pinned SDK auditor; recorded successful converter maps them to final NIDs. '
               'Converted layout retained sections verified. Signed SELF inspected by pinned tool. '
               'No independent NID-runtime ABI verification or console execution.'}
(root/'AUDIT-CHAIN.json').write_text(json.dumps(audit,indent=2))
param=json.loads((app/'sce_sys/param.json').read_text())
content=read('CONTENT.json')
assert content['all_hashes_verified']
manifest={'schema':1,'source_revision':receipt['source_revision']+' + captured local inputs',
    'build_id':receipt['build_id'],'app_root':str(app),'title_id':param['titleId'],
    'title_name':param['localizedParameters'][param['localizedParameters']['defaultLanguage']]['titleName'],
    'content_version':param['contentVersion'],'param':art(app/'sce_sys/param.json'),
    'eboot':{**art(app/'eboot.bin'),'magic_hex':(app/'eboot.bin').read_bytes()[:4].hex()},
    'elf':art(root/'eboot.elf'),'icon':{**art(app/'sce_sys/icon0.png'),'dimensions':[512,512]},
    'dependencies':[{key:item[key] for key in ['path','sha256']} for item in content['files']
                    if pathlib.Path(item['path']) not in [app/'eboot.bin',app/'sce_sys/param.json',app/'sce_sys/icon0.png']],
    'rollback':{'eboot':art(pathlib.Path(sys.argv[2])/'eboot.bin'),
                'param':art(pathlib.Path(sys.argv[2])/'app/PPSA99875/sce_sys/param.json')},
    'recipe':{'cwd':str(workspace),'argv':['python',str(snapshot/'build-native.py'),'--build-id',receipt['build_id'],'--stage','NEW_EMPTY_STAGE'],
              'environment_notes':'Pinned native recipe uses the recorded host build and private GRSEAF module. Never overwrite accepted candidates.',
              'files':[art(root/'FINALIZATION.json'),art(root/'link-args.json'),art(snapshot/'build-native.py'),art(root/'commands.json')]},
    'pairing_receipt':{**art(root/'FINALIZATION.json'),'eboot_hash_field':'eboot.sha256','elf_hash_field':'elf.sha256'},
    'audits':[{**art(root/'AUDIT-CHAIN.json'),'subject':'elf','subject_hash_field':'elf.sha256',
               'covers':['imports','runtime_layout','self_integrity'],
               'assertions':[{'field':key,'equals':True} for key in ['imports_passed','runtime_layout_passed','self_integrity_passed']]}]}
# Run recipe in its recorded source location; the snapshot is evidence, not a relocated workspace.
manifest['recipe']['argv'][1]=str(pathlib.Path(__file__).resolve().with_name('build-package.py'))
manifest['recipe']['argv'].extend(['--rollback', sys.argv[2]])
if receipt.get('host_attestation'):
    manifest['recipe']['argv'].extend(['--host-build', receipt['host_build']])
    manifest['recipe']['files'].append(receipt['host_attestation'])
if receipt.get('include_ps5_menu'):
    manifest['recipe']['argv'].append('--include-ps5-menu')
if receipt.get('trace_boot'):
    manifest['recipe']['argv'].append('--trace-boot')
if receipt.get('use_title_heap'):
    manifest['recipe']['argv'].append('--use-title-heap')
for dependency in manifest['dependencies']:
    path=pathlib.Path(dependency['path'])
    if path.stat().st_size==0:
        relative=path.relative_to(app/'sys/Load/GraphicMods')
        upstream=workspace/'source/ModernGekko/vendor/dolphin/Data/Sys/Load/GraphicMods'/relative
        assert path.suffix=='.txt' and upstream.is_file() and upstream.stat().st_size==0
        assert sha(upstream)==dependency['sha256']
        dependency.update(allow_empty=True,empty_reason='Unchanged upstream Dolphin graphic-mod game-selector marker; upstream and baseline hashes verified.')
(root/'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
result=subprocess.run(['python','C:/Users/gumbreezy/.codex/skills/ps5-build-package/scripts/check_package.py',
                       str(root/'PACKAGE-MANIFEST.json')],capture_output=True,text=True)
(root/'PACKAGE-CHECK.json').write_text(result.stdout)
summary=json.loads(result.stdout)
print(json.dumps({key:summary[key] for key in ['status','boot_verified','installed','errors']}));print(result.stderr)
raise SystemExit(result.returncode)


