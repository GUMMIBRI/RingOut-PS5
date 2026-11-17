# Read-only roster inventory

Run `python inventory.py PATH_TO_ROOT_OLK --platform gamecube` or use `--platform xbox` and redirect JSON to a private file. The chosen platform determines numbered-pack byte order and the expected stock guest; it does not establish disc identity. OLNK headers are little-endian on both platforms. JSON records complete 39-slot character blocks starting at `/4/46`, known guest fighter IDs separately from `/2` UI indices, and size, prefix and SHA-256 per slot and heuristically recognized numbered-pack part. Empty entries are holes. No asset payload is exported. The hashes and prefixes describe private game data; keep the output private.

The parser rejects tables or nonempty entries outside their immediate container, including nested containers. Numbered-pack identification is heuristic, and a malformed or non-pack entry is simply not labeled as a pack. Other fighter-to-block mappings are not established here. This is an inventory, not a converter or proof of runtime compatibility.

Tests: `python -m unittest -v test_inventory` from this directory.

The format and guest indices were informed by `C:/SC2/tools/guests/olnk.py` and `roster.py`, SPDX GPL-3.0-or-later. This tool is GPL-3.0-or-later; see LICENSE-GPL-3.0 in this directory.
