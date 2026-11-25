# SPDX-License-Identifier: GPL-2.0-or-later
"""Check linked RADV dispatch tables for Dolphin's required device functions.

This is a static ELF check; it does not prove target driver lookup or gameplay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--elf', required=True, type=Path)
parser.add_argument('--entrypoints', required=True, type=Path)
parser.add_argument('--nm', required=True)
parser.add_argument('--readelf', required=True)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
source = args.entrypoints.read_text()
required = re.findall(r'VULKAN_DEVICE_ENTRY_POINT\((vk\w+),\s*true\)', source)
if not required or len(set(required)) != len(required):
    raise SystemExit('missing or duplicate required device entrypoints')
raw_symbols = subprocess.check_output([args.nm, '-S', '--defined-only', str(args.elf)], text=True)
symbols = {}
for line in raw_symbols.splitlines():
    fields = line.split()
    if len(fields) >= 4 and fields[-2] not in ('U', 'u', 'w', 'v'):
        symbols[fields[-1]] = (int(fields[0], 16), int(fields[1], 16))
raw_relocs = subprocess.check_output([args.readelf, '-r', str(args.elf)], text=True)
relocations = []
for line in raw_relocs.splitlines():
    match = re.match(r'^\s*([0-9a-fA-F]+)\s+\S+\s+R_X86_64_RELATIVE\s+([0-9a-fA-F]+)\s*$', line)
    if match: relocations.append((int(match.group(1), 16), int(match.group(2), 16)))
tables = [(n, *symbols[n]) for n in ('radv_device_entrypoints', 'vk_common_device_entrypoints',
                                      'wsi_device_entrypoints') if n in symbols]
rows = []
for function in required:
    providers = [prefix + function[2:] for prefix in ('radv_', 'vk_common_', 'wsi_')
                 if prefix + function[2:] in symbols]
    hits = [{'provider': provider, 'table': table, 'relocation': hex(offset)}
            for provider in providers for table, start, size in tables for offset, addend in relocations
            if start <= offset < start + size and addend == symbols[provider][0]]
    rows.append({'function': function, 'matches': hits})
with args.elf.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
missing = [row['function'] for row in rows if not row['matches']]
result = {'status': 'FAIL' if missing else 'PASS', 'elf_sha256': digest, 'required_count': len(rows),
          'missing': missing, 'functions': rows,
          'scope': 'ELF dispatch-table relocations; target runtime lookup is not verified'}
args.output.write_text(json.dumps(result, indent=2))
print(json.dumps({k: result[k] for k in ('status', 'required_count', 'missing')}))
raise SystemExit(bool(missing))
