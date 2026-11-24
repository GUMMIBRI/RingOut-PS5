# SPDX-License-Identifier: GPL-2.0-or-later
"""Rebuild and attest the source-matched PS5 host archives, without packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--host-build', required=True)
parser.add_argument('--jobs', type=int, default=2)
args = parser.parse_args()
host = Path(args.host_build).resolve()
source = Path(__file__).resolve().parents[2]
ninja = Path('C:/.pe/tools/ninja/ninja.exe')

def git(*args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

cache = (host / 'CMakeCache.txt').read_text(encoding='utf-8')
home = next((line.split('=', 1)[1] for line in cache.splitlines()
             if line.startswith('CMAKE_HOME_DIRECTORY:INTERNAL=')), '')
if Path(home).resolve() != (source / 'ModernGekko').resolve():
    parser.error('CMake build belongs to a different source checkout')
if git('status', '--porcelain', '--untracked-files=no'):
    parser.error('tracked source must be clean')
revision = git('rev-parse', 'HEAD')
command = [str(ninja), '-j', str(args.jobs), 'libmoderngekko.a']
result = subprocess.run(command, cwd=host, capture_output=True, text=True)
(host / 'attested-build.log').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
if result.returncode or git('rev-parse', 'HEAD') != revision or git('status', '--porcelain', '--untracked-files=no'):
    raise SystemExit('host build failed or source changed; no attestation written')
archives = {p.relative_to(host).as_posix(): digest(p) for p in host.rglob('*.a') if p.is_file()}
if not archives or 'libmoderngekko.a' not in archives:
    raise SystemExit('host archive missing; no attestation written')
receipt = {'status': 'success', 'source_root': str(source), 'source_revision': revision,
           'build_ninja_sha256': digest(host / 'build.ninja'), 'ninja_sha256': digest(ninja),
           'command': command, 'build_log_sha256': digest(host / 'attested-build.log'),
           'archives': archives}
(host / 'BUILD-ATTESTATION.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('attested', len(archives), 'archives for', revision)
