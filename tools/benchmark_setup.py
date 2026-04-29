#!/usr/bin/env python3
"""
BlenderRigConvert 환경 설정 벤치마크

시스템 Python으로 실행 (.venv 불필요):
  python tools/benchmark_setup.py

다른 PC와 비교: 생성된 benchmark_result.txt 공유
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────────
# Windows cmd 기본 인코딩(CP949)에서도 한글이 깨지지 않도록
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
_IS_WIN = sys.platform == "win32"
VENV_PIP = VENV_DIR / ("Scripts/pip" if _IS_WIN else "bin/pip")
RESULT_FILE = REPO_ROOT / "benchmark_result.txt"

# ── 출력 헬퍼 ─────────────────────────────────────────────────────────
SEP = "=" * 48
THIN = "─" * 48


def header(text: str) -> None:
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)


def step_header(n: int, total: int, text: str) -> None:
    print(f"\n[{n}/{total}] {text}")


def ok(elapsed: float) -> None:
    print(f"  완료  ({elapsed:.1f} s)")


def warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


# ── 스피너 ────────────────────────────────────────────────────────────
def run_with_spinner(args: list[str], *, cwd: Path | None = None) -> tuple[float, int, str, str]:
    """subprocess 실행하면서 터미널에 점을 찍어 진행 표시."""
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or REPO_ROOT),
    )
    start = time.perf_counter()
    stop_event = threading.Event()

    def _dots() -> None:
        while not stop_event.is_set():
            print(".", end="", flush=True)
            time.sleep(0.5)

    dot_thread = threading.Thread(target=_dots, daemon=True)
    dot_thread.start()
    stdout, stderr = proc.communicate()
    stop_event.set()
    dot_thread.join()

    elapsed = time.perf_counter() - start
    return (
        elapsed,
        proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


# ── 시스템 정보 ───────────────────────────────────────────────────────
def collect_system_info() -> dict[str, str]:
    info: dict[str, str] = {}
    info["OS"] = f"{platform.system()} {platform.release()} ({platform.version()[:24]})"
    info["CPU"] = platform.processor() or platform.machine()
    info["코어"] = str(os.cpu_count() or "?")
    info["Python"] = f"{platform.python_version()} ({platform.python_implementation()})"
    try:
        import psutil  # type: ignore[import-untyped]

        ram_gb = psutil.virtual_memory().total / 1024**3
        info["RAM"] = f"{ram_gb:.1f} GB"
    except ImportError:
        info["RAM"] = "N/A (psutil 없음)"
    return info


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> int:
    started_at = datetime.now()
    timings: list[tuple[str, float]] = []

    header("BlenderRigConvert 환경 설정 벤치마크")
    sys_info = collect_system_info()
    print(f"  시작 시각  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    for k, v in sys_info.items():
        print(f"  {k:<6} : {v}")

    # ── Step 1: venv 초기화 ───────────────────────────────────────────
    step_header(1, 3, "venv 초기화")
    if VENV_DIR.exists():
        print("  기존 .venv 삭제 중... ", end="", flush=True)
        shutil.rmtree(VENV_DIR)
        print("완료")
    print("  python -m venv .venv ", end="", flush=True)
    elapsed, rc, _, stderr = run_with_spinner([sys.executable, "-m", "venv", str(VENV_DIR)])
    if rc != 0:
        print()
        print(f"  오류: {stderr.strip()}")
        return rc
    ok(elapsed)
    timings.append(("venv 초기화", elapsed))

    # ── Step 2: 패키지 설치 ───────────────────────────────────────────
    step_header(2, 3, "패키지 설치 (ruff, pytest)")
    print("  pip install ruff pytest ", end="", flush=True)
    elapsed, rc, _, stderr = run_with_spinner(
        [str(VENV_PIP), "install", "ruff", "pytest", "--quiet"]
    )
    if rc != 0:
        print()
        print(f"  오류: {stderr.strip()[:300]}")
        return rc
    ok(elapsed)
    timings.append(("패키지 설치", elapsed))

    # ── Step 3: 애드온 빌드 & Blender 설치 ───────────────────────────
    step_header(3, 3, "애드온 빌드 및 Blender 설치")
    install_script = REPO_ROOT / "tools" / "install_blender_addon.py"
    print("  install_blender_addon.py --install ", end="", flush=True)
    elapsed, rc, stdout, stderr = run_with_spinner(
        [sys.executable, str(install_script), "--install"]
    )
    if rc != 0:
        print()
        warn("애드온 설치 실패 (Blender 경로가 없을 수 있습니다)")
        if stderr.strip():
            print(f"  {stderr.strip()[:300]}")
    else:
        printed_newline = False
        for line in stdout.splitlines():
            if any(kw in line for kw in ("Installed", "Built", "installed")):
                if not printed_newline:
                    print()
                    printed_newline = True
                print(f"  {line.strip()}")
    ok(elapsed)
    timings.append(("애드온 빌드/설치", elapsed))

    # ── 결과 요약 ─────────────────────────────────────────────────────
    total = sum(t for _, t in timings)
    print(f"\n{SEP}")
    print("  결과 요약")
    print(SEP)
    for label, t in timings:
        print(f"  {label:<16} : {t:6.1f} s")
    print(THIN)
    print(f"  {'총 소요 시간':<16} : {total:6.1f} s")
    print(SEP)

    # ── benchmark_result.txt 저장 ─────────────────────────────────────
    lines = [
        "BlenderRigConvert 환경 설정 벤치마크",
        f"시작 시각  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for k, v in sys_info.items():
        lines.append(f"{k:<6} : {v}")
    lines += ["", "── 타이밍 ──"]
    for label, t in timings:
        lines.append(f"{label:<16} : {t:.1f} s")
    lines.append(f"{'총 소요 시간':<16} : {total:.1f} s")
    RESULT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  결과를 {RESULT_FILE.name} 에 저장했습니다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
