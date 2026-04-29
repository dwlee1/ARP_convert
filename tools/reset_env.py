#!/usr/bin/env python3
"""
벤치마크/녹화 전 클린 상태 초기화

삭제 대상:
  .venv/   — 가상환경
  dist/    — 애드온 빌드 산출물

사용법:
  python tools/reset_env.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    REPO_ROOT / ".venv",
    REPO_ROOT / "dist",
]


def remove(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
        print(f"  삭제됨  {path.relative_to(REPO_ROOT)}/")
    else:
        print(f"  없음    {path.relative_to(REPO_ROOT)}/")


def main() -> int:
    print("── 클린 상태 초기화 ─────────────────────")
    for target in TARGETS:
        remove(target)
    print("─────────────────────────────────────────")
    print("완료. 이제 녹화를 시작하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
