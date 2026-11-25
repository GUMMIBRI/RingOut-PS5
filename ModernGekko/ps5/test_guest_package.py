import hashlib, json, pathlib, tempfile, unittest
from guest_package import guest_files

class GuestPackageTest(unittest.TestCase):
 def test_accepts_only_matching_game_and_archive(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);base=root/'stock.olk';base.write_bytes(b'stock')
   guest=root/'guests';guest.mkdir();archive=guest/'root-guests.olk';archive.write_bytes(b'converted')
   digest=lambda value:hashlib.sha1(value).hexdigest()
   manifest={'format':2,'disc':'GRSEAF','gc_root_sha1':digest(b'stock'),'size':9,'sha1':digest(b'converted')}
   (guest/'guests.json').write_text(json.dumps(manifest))
   self.assertEqual({p.name for p in guest_files(guest,base)},{'guests.json','root-guests.olk'})
   base.write_bytes(b'other')
   with self.assertRaises(ValueError):guest_files(guest,base)
   base.write_bytes(b'stock');archive.write_bytes(b'tampered!')
   with self.assertRaises(ValueError):guest_files(guest,base)

if __name__=='__main__':unittest.main()
