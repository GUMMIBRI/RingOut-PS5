import hashlib, json, pathlib, shutil, subprocess, sys, tempfile, unittest
SCRIPT=pathlib.Path(__file__).with_name('build-package.py')
ROLLBACK=pathlib.Path('C:/SC2/Taki-RingOut/aot-work/ps5-aot-grseaf-r1/staged-native-r7')
class RecipePlanTest(unittest.TestCase):
 def test_dry_run_and_freshness(self):
  with tempfile.TemporaryDirectory(prefix='ringout-plan-') as t:
   stage=pathlib.Path(t)/'new-stage'
   cmd=[sys.executable,str(SCRIPT),'--stage',str(stage),'--build-id','native-test','--rollback',str(ROLLBACK),'--include-ps5-menu','--dry-run']
   here=SCRIPT.resolve().parent
   if here != (here.parents[2]/'source/ModernGekko/ps5').resolve():
    result=subprocess.run(cmd,capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0)
    self.assertIn('different source checkout',result.stderr)
    self.assertFalse(stage.exists())
    return
   result=subprocess.run(cmd,capture_output=True,text=True,check=True)
   plan=json.loads(result.stdout);self.assertFalse(stage.exists());self.assertEqual(len(plan['plan']),5)
   self.assertIn('--include-ps5-menu',plan['plan'][0]);self.assertEqual(plan['stage'],str(stage))
   stage.mkdir();(stage/'occupied').write_text('keep')
   bad=subprocess.run(cmd,capture_output=True,text=True)
   self.assertNotEqual(bad.returncode,0);self.assertEqual((stage/'occupied').read_text(),'keep')
 def test_missing_rollback(self):
  with tempfile.TemporaryDirectory(prefix='ringout-plan-') as t:
   cmd=[sys.executable,str(SCRIPT),'--stage',str(pathlib.Path(t)/'stage'),'--build-id','x','--rollback',str(pathlib.Path(t)/'missing'),'--dry-run']
   self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
 def test_unattested_host_build_rejected_before_staging(self):
  with tempfile.TemporaryDirectory(prefix='ringout-host-') as t:
   stage=pathlib.Path(t)/'stage'
   native=SCRIPT.with_name('build-native.py')
   cmd=[sys.executable,str(native),'--stage',str(stage),'--build-id','x','--host-build',t]
   result=subprocess.run(cmd,capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0)
   self.assertIn('requires BUILD-ATTESTATION.json',result.stderr)
   self.assertFalse(stage.exists())
 def test_host_attestation_rejects_changed_game_module(self):
  if not shutil.which('git'): self.skipTest('git is required')
  with tempfile.TemporaryDirectory(prefix='ringout-attest-') as t:
   root=pathlib.Path(t)/'repo'; script=root/'ModernGekko/ps5/build-native.py'
   script.parent.mkdir(parents=True);shutil.copyfile(SCRIPT.with_name('build-native.py'),script)
   subprocess.run(['git','init','-q',str(root)],check=True)
   subprocess.run(['git','-C',str(root),'add','ModernGekko'],check=True)
   subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
   revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
   host=pathlib.Path(t)/'host';host.mkdir(); (host/'build.ninja').write_bytes(b'fixture')
   module=pathlib.Path(t)/'game.a';module.write_bytes(b'changed')
   attestation={'status':'success','source_root':str(root),'source_revision':revision,
    'build_ninja_sha256':hashlib.sha256(b'fixture').hexdigest(),
    'game_module':{'path':str(module),'sha256':hashlib.sha256(b'original').hexdigest()}}
   (host/'BUILD-ATTESTATION.json').write_text(json.dumps(attestation))
   stage=pathlib.Path(t)/'stage';result=subprocess.run([sys.executable,str(script),'--stage',str(stage),'--build-id','x','--host-build',str(host)],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('game module hash differs',result.stderr);self.assertFalse(stage.exists())
 def test_dry_run_keeps_private_source_arguments(self):
  with tempfile.TemporaryDirectory(prefix='ringout-guest-plan-') as t:
   cmd=[sys.executable,str(SCRIPT),'--stage',str(pathlib.Path(t)/'stage'),'--build-id','x',
        '--rollback',str(ROLLBACK),'--host-build',str(pathlib.Path(t)/'host'),
        '--guest-dir',str(pathlib.Path(t)/'guests'),'--asset-source',str(pathlib.Path(t)/'app'),'--trace-vulkan','--dry-run']
   plan=json.loads(subprocess.run(cmd,capture_output=True,text=True,check=True).stdout)['plan']
   self.assertIn('--host-build',plan[0]);self.assertIn('--trace-vulkan',plan[0]);self.assertIn('--guest-dir',plan[1]);self.assertIn('--asset-source',plan[1])
if __name__=='__main__':unittest.main()
