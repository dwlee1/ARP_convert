"""Windows용 PyInstaller 빌드 스크립트."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DIST_DIR = SCRIPT_DIR / "dist"
BUILD_DIR = SCRIPT_DIR / "build"
SPEC_DIR = SCRIPT_DIR
SCAN_SCRIPT = SCRIPT_DIR / "scan_blend_identity.py"
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_blend_identity.py"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "blend_identity_scan",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--add-data",
        f"{EXTRACT_SCRIPT};.",
        str(SCAN_SCRIPT),
    ]

    result = subprocess.run(cmd, cwd=SCRIPT_DIR.parent.parent)
    if result.returncode != 0:
        return result.returncode

    print()
    print("Build complete:")
    print(f"  {DIST_DIR / 'blend_identity_scan.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
