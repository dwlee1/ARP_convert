"""Edit/Write 후 자동 실행되는 애드온 동기화 스크립트.

프로젝트 scripts/ 파일을 Blender addons/arp_rig_convert/ 패키지로 복사한다.
arp_convert_addon.py → __init__.py 로 이름이 바뀐다.
"""

import os
import shutil
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJECT, "scripts")

APPDATA = os.environ.get("APPDATA", "")
ADDON_DIR = os.path.join(
    APPDATA, "Blender Foundation", "Blender", "4.5", "scripts", "addons", "arp_rig_convert"
)

FILE_MAP = {
    "arp_convert_addon.py": "__init__.py",
    "skeleton_analyzer.py": "skeleton_analyzer.py",
    "arp_utils.py": "arp_utils.py",
    "weight_transfer_rules.py": "weight_transfer_rules.py",
    "mcp_bridge.py": "mcp_bridge.py",
}


def sync():
    if not os.path.isdir(ADDON_DIR):
        print(f"[sync_addon] addon dir not found: {ADDON_DIR}", file=sys.stderr)
        return 1

    copied = []
    for src_name, dst_name in FILE_MAP.items():
        src = os.path.join(SCRIPTS, src_name)
        dst = os.path.join(ADDON_DIR, dst_name)
        if not os.path.isfile(src):
            continue
        if os.path.isfile(dst) and os.path.getmtime(src) <= os.path.getmtime(dst):
            continue
        shutil.copy2(src, dst)
        copied.append(f"{src_name} -> {dst_name}")

    if copied:
        print(f"[sync_addon] {', '.join(copied)}")
    return 0


if __name__ == "__main__":
    sys.exit(sync())
