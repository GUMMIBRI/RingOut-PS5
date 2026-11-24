import json, pathlib, subprocess, sys, tempfile, unittest
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
if __name__=='__main__':unittest.main()
