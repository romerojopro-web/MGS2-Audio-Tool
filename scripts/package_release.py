#!/usr/bin/env python3
"""
package_release.py — Build the shareable ZIP of the tool, and nothing else.

The working copy of this project contains real game data (multi-GB dumps in
`tests/mgs2_substance_2003/`, real `.sdx` banks in `scripts/sdx_mgs2_MC/`,
extracted WAVs at the root…) which is copyrighted and must never be shared.
Rather than zipping the folder and hoping, this script builds the archive
from an explicit allowlist — anything not listed simply cannot leak.

Usage (from the project root):

    python scripts/package_release.py            # writes dist/mgs2-audio-tool-<version>.zip
    python scripts/package_release.py --list     # only print what would be packed
"""

import argparse
import os
import re
import sys
import zipfile

# What ships. Directories are walked recursively but only for the listed
# extensions — game data (.dat/.sdx/.sdt/.wav/.bundle…) never matches.
PACKED_DIRS = {
    "mgs2_audio": (".py",),
    "docs": (".md",),
    "tests": (".py",),           # the suite is synthetic; real data is opt-in
    "scripts": (".py",),
}
PACKED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "run.py",
    "pytest.ini",
]


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_version(root: str) -> str:
    with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"##\s+([\w.]+)", line)
            if m and m.group(1).lower() != "unreleased":
                return m.group(1)
    return "dev"


def collect(root: str):
    for rel in PACKED_FILES:
        if os.path.isfile(os.path.join(root, rel)):
            yield rel
    for d, exts in PACKED_DIRS.items():
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, d)):
            dirnames[:] = [n for n in dirnames if n != "__pycache__"]
            for name in sorted(filenames):
                if name.endswith(exts):
                    full = os.path.join(dirpath, name)
                    yield os.path.relpath(full, root).replace(os.sep, "/")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--list", action="store_true",
                    help="print the file list without writing the archive")
    args = ap.parse_args()

    root = project_root()
    files = list(collect(root))

    if args.list:
        print("\n".join(files))
        print(f"\n{len(files)} files")
        return 0

    version = read_version(root)
    out_dir = os.path.join(root, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"mgs2-audio-tool-{version}.zip")

    top = f"mgs2-audio-tool-{version}"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(root, rel), f"{top}/{rel}")

    size = os.path.getsize(out)
    print(f"{out}  ({len(files)} files, {size:,} bytes)")
    if size > 20 * 1024 * 1024:
        print("WARNING: archive suspiciously large for source code — "
              "check nothing unexpected slipped in", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
