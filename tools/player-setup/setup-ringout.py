# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a player's GameCube game files and PS5 module from their own disc."""

import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import importlib

HERE = Path(__file__).resolve().parent
SECTOR = 2048
MAX_DIRECTORY_BYTES = 4 * 1024 * 1024


def donor_kind(path, converters):
    """Inspect only bounded disc metadata while discovering optional donors."""
    xiso = converters.xiso
    size = path.stat().st_size
    with path.open("rb") as stream:
        stream.seek(16 * SECTOR)
        header = stream.read(SECTOR)
        if len(header) == SECTOR and header[1:6] == b"CD001" and header[8:19] == b"PLAYSTATION":
            offset = struct.unpack_from("<I", header, 158)[0] * SECTOR
            length = struct.unpack_from("<I", header, 166)[0]
            if 0 < length <= MAX_DIRECTORY_BYTES and offset + length <= size:
                entries = converters.ps2iso.open_image(path)
                if "ROOT.OLK" in entries and converters.ps2iso.SLUS_20643.elf_name in entries:
                    return "heihachi"
            return None

        for partition in xiso.PARTITIONS:
            stream.seek(partition + 32 * SECTOR)
            header = stream.read(28)
            if len(header) != 28 or header[:20] != xiso.MAGIC:
                continue
            sector, length = struct.unpack_from("<II", header, 20)
            if 0 < length <= MAX_DIRECTORY_BYTES and partition + sector * SECTOR + length <= size:
                entries = xiso.open_image(path)
                if xiso.find(entries, "root.olk") and any(
                    xiso.find(entries, name) for name in converters.releases.EXECUTABLES
                ):
                    return "spawn"
            return None
    return None


def discover(gamecube, supplied):
    if all(supplied.values()):
        return supplied
    prepare = importlib.import_module("prepare-ringout")
    converters = prepare.converters()
    found = {name: [] for name, path in supplied.items() if path is None}
    parse_errors = (converters.xiso.ImageError, converters.ps2iso.Refusal, struct.error)
    for path in sorted(gamecube.parent.iterdir()):
        if path == gamecube or path.is_symlink() or path.suffix.lower() not in (".iso", ".xiso"):
            continue
        if path.is_file():
            try:
                name = donor_kind(path, converters)
            except parse_errors:
                continue
            if name in found:
                found[name].append(path)
    for name, paths in found.items():
        if len(paths) > 1:
            raise ValueError(f"Found multiple {name} donors. Choose one with --{name}.")
        if paths:
            supplied[name] = paths[0]
    return supplied


def run_script(name, *args):
    subprocess.run([sys.executable, "-B", str(HERE / name), *map(str, args)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gamecube", type=Path, help="US GameCube ISO or GCM (GRSEAF)")
    for name in ("output", "sdk", "llvm"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("spawn", "heihachi", "cc"):
        parser.add_argument("--" + name, type=Path)
    for name in ("cmake", "ninja"):
        parser.add_argument("--" + name, default=name)
    parser.add_argument("--stock", action="store_true", help="Skip donor discovery and imports.")
    args = parser.parse_args()
    gamecube = args.gamecube.resolve(strict=True)
    if args.stock and (args.spawn or args.heihachi):
        parser.error("--stock cannot be combined with explicit donors")
    try:
        toolchain = {name: shutil.which(getattr(args, name)) for name in ("cmake", "ninja")}
        if not all(toolchain.values()):
            raise ValueError("CMake and Ninja must be on PATH or supplied explicitly.")
        args.sdk = args.sdk.resolve()
        args.llvm = args.llvm.resolve()
        for required in (args.sdk / "target/include/stdlib.h", args.llvm / "clang.exe",
                         args.llvm / "ld.lld.exe"):
            if not required.is_file():
                raise ValueError(f"Missing SDK or LLVM file: {required}")
        donors = {"spawn": args.spawn, "heihachi": args.heihachi}
        if not args.stock:
            discover(gamecube, donors)
        compiler = args.cc or shutil.which("zig")
        if any(donors.values()) and not compiler:
            raise ValueError("Guest audio conversion requires Zig on PATH or --cc PATH\u005cto\u005czig.exe.")

        output = args.output.resolve()
        output.mkdir()
        work = output / "work"
        work.mkdir()
        game_args = ["prepare", gamecube, "--output", output]
        for name, path in donors.items():
            if path:
                game_args.extend(("--" + name, path))
        if compiler:
            game_args.extend(("--cc", compiler))
        run_script("prepare-ringout.py", *game_args)
        run_script("prepare-own-disc.py", "--iso", gamecube, "--out", work / "program")
        run_script("build-own-archive.py", "--input", work / "program", "--source", HERE / "source",
                   "--dolrecomp", HERE / "bin/dolrecomp.exe", "--llvm", args.llvm, "--sdk", args.sdk,
                   "--cmake", toolchain["cmake"], "--ninja", toolchain["ninja"], "--out", work / "aot")
        run_script("build-own-prx.py", "--archive-dir", work / "aot", "--source", HERE / "source",
                   "--foundation", HERE / "foundation", "--sdk", args.sdk, "--llvm", args.llvm,
                   "--converter", HERE / "bin/ps5-native-prx-tool.exe", "--output", work / "native")
        run_script("prepare-ringout.py", "check", output / "game")
        (output / "sce_module").mkdir()
        shutil.copy2(work / "native/gGRSEAF_recomp.prx", output / "sce_module/gGRSEAF_recomp.prx")
        print(f"Ready to copy: {output / 'game'} and {output / 'sce_module'}")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"RingOut setup stopped: {error}\n")


if __name__ == "__main__":
    main()
