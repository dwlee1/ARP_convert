#!/usr/bin/env python3
"""
Build and optionally install the Blender 4.5 add-on package for this repo.

Usage:
  python tools/install_blender_addon.py
  python tools/install_blender_addon.py --install
  python tools/install_blender_addon.py --install --addons-dir "C:/path/to/Blender/4.5/scripts/addons"
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path

PACKAGE_NAME = "arp_rig_convert"
DEFAULT_BLENDER_VERSION = "4.5"
MODULE_COPY_MAP = {
    "scripts/arp_convert_addon.py": "__init__.py",
    "scripts/arp_utils.py": "arp_utils.py",
    "scripts/skeleton_analyzer.py": "skeleton_analyzer.py",
    "scripts/skeleton_detection.py": "skeleton_detection.py",
    "scripts/weight_transfer_rules.py": "weight_transfer_rules.py",
    "scripts/arp_mapping.py": "arp_mapping.py",
    "scripts/arp_retarget.py": "arp_retarget.py",
    "scripts/arp_build_helpers.py": "arp_build_helpers.py",
    "scripts/arp_def_separator.py": "arp_def_separator.py",
    "scripts/arp_cc_bones.py": "arp_cc_bones.py",
    "scripts/arp_weight_xfer.py": "arp_weight_xfer.py",
    "scripts/arp_foot_guides.py": "arp_foot_guides.py",
    "scripts/arp_fixture_io.py": "arp_fixture_io.py",
    "scripts/arp_props.py": "arp_props.py",
    "scripts/arp_ui.py": "arp_ui.py",
    "scripts/arp_role_icons.py": "arp_role_icons.py",
    "scripts/arp_viewport_handler.py": "arp_viewport_handler.py",
    "scripts/arp_ops_preview.py": "arp_ops_preview.py",
    "scripts/arp_ops_roles.py": "arp_ops_roles.py",
    "scripts/arp_ops_build.py": "arp_ops_build.py",
    "scripts/arp_ops_bake_regression.py": "arp_ops_bake_regression.py",
}
RESOURCE_DIRS = (
    "mapping_profiles",
    "remap_presets",
    "regression_fixtures",
)
IGNORES = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_appdata_root() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def detect_addons_dir(blender_version: str) -> Path:
    return (
        detect_appdata_root()
        / "Blender Foundation"
        / "Blender"
        / blender_version
        / "scripts"
        / "addons"
    )


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_package(output_root: Path) -> Path:
    root = repo_root()
    package_dir = output_root / PACKAGE_NAME
    ensure_clean_dir(package_dir)

    for src_rel, dst_name in MODULE_COPY_MAP.items():
        src_path = root / src_rel
        if not src_path.exists():
            raise FileNotFoundError(f"Required source file not found: {src_path}")
        shutil.copy2(src_path, package_dir / dst_name)

    for resource_name in RESOURCE_DIRS:
        src_dir = root / resource_name
        if not src_dir.is_dir():
            continue
        shutil.copytree(src_dir, package_dir / resource_name, ignore=IGNORES)

    return package_dir


def build_zip(package_dir: Path, output_root: Path, blender_version: str) -> Path:
    zip_path = output_root / f"{PACKAGE_NAME}_blender_{blender_version.replace('.', '_')}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(package_dir.rglob("*")):
            if file_path.is_dir():
                continue
            arcname = Path(PACKAGE_NAME) / file_path.relative_to(package_dir)
            archive.write(file_path, arcname.as_posix())

    return zip_path


def install_package(package_dir: Path, addons_dir: Path) -> Path:
    addons_dir.mkdir(parents=True, exist_ok=True)
    install_dir = addons_dir / PACKAGE_NAME
    if install_dir.exists():
        shutil.rmtree(install_dir)
    shutil.copytree(package_dir, install_dir, ignore=IGNORES)
    return install_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and optionally install the BlenderRigConvert add-on package."
    )
    parser.add_argument(
        "--blender-version",
        default=DEFAULT_BLENDER_VERSION,
        help=f"Target Blender version directory. Default: {DEFAULT_BLENDER_VERSION}",
    )
    parser.add_argument(
        "--output-dir",
        default="dist/blender_addon",
        help="Directory where the package folder and zip should be created.",
    )
    parser.add_argument(
        "--addons-dir",
        default="",
        help="Override the Blender add-ons directory. Default: APPDATA-based Blender path.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Copy the built package into Blender's add-ons directory after packaging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = (repo_root() / args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    package_dir = build_package(output_root)
    zip_path = build_zip(package_dir, output_root, args.blender_version)

    print(f"Built package folder: {package_dir}")
    print(f"Built installable zip: {zip_path}")

    if args.install:
        addons_dir = (
            Path(args.addons_dir).expanduser().resolve()
            if args.addons_dir
            else detect_addons_dir(args.blender_version)
        )
        install_dir = install_package(package_dir, addons_dir)
        print(f"Installed add-on folder: {install_dir}")
        print("In Blender, enable 'ARP Rig Convert' from Preferences > Add-ons.")
    else:
        print("Add --install to copy the package into Blender's add-ons directory.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
