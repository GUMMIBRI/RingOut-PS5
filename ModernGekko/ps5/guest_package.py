# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate private guest data against the exact GameCube archive to package."""
import hashlib
import json
from pathlib import Path

def sha1(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha1').hexdigest()

def guest_files(directory, game_archive):
    directory = Path(directory).resolve()
    manifest_path = directory / 'guests.json'
    archive = directory / 'root-guests.olk'
    if manifest_path.is_symlink() or archive.is_symlink():
        raise ValueError('guest files must not be symbolic links')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('format') != 2 or manifest.get('disc') != 'GRSEAF' or
        sha1(Path(game_archive)) != manifest.get('gc_root_sha1') or
        not archive.is_file() or archive.stat().st_size != manifest.get('size') or
        sha1(archive) != manifest.get('sha1')):
        raise ValueError('private guest archive does not match this game and its manifest')
    result = [manifest_path, archive]
    for name in ('intro-spawn.sfd', 'intro-heihachi.sfd'):
        p = directory / name
        if p.is_symlink(): raise ValueError('guest files must not be symbolic links')
        if p.is_file(): result.append(p)
    return result
