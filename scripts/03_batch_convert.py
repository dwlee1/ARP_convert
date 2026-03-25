"""
03. 배치 변환
==============
Asset/BlenderFile/ 하위의 .blend 파일을 일괄 변환.
Blender 외부에서 실행 (일반 Python).

사용법:
  python scripts/03_batch_convert.py                    # 미변환 파일 목록 (dry-run)
  python scripts/03_batch_convert.py --run              # 실제 변환 실행
  python scripts/03_batch_convert.py --run --filter normal/fox  # 특정 폴더만
  python scripts/03_batch_convert.py --run --workers 2  # 병렬 처리
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

# 프로젝트 루트 (이 스크립트의 상위 폴더)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Blender 실행 파일 경로
BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"

# 검색 대상 루트
ASSET_ROOT = os.path.join(PROJECT_ROOT, "Asset", "BlenderFile")

# 파이프라인 스크립트
PIPELINE_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "pipeline_runner.py")

# 디렉토리 → 프로필 매핑
PROFILE_MAP = {
    "normal": "custom_quadruped",
    "sea": "custom_quadruped",
    "Sup_01": "custom_quadruped",
    "Sup_02": "custom_quadruped",
    "2024": "custom_quadruped",
    "2025": "custom_quadruped",
    "2026": "custom_quadruped",
    # "bird":  "bird",  # 프로필 미작성 — 추후 활성화
}

# 변환 제외 패턴
SKIP_PATTERNS = [
    ".blend1",  # 백업 파일
    "_RigConvert",  # 이미 변환된 사본
    "Effect",  # 이펙트 폴더
    "etc",  # 기타 폴더
]

# 기본 타임아웃 (초)
DEFAULT_TIMEOUT = 600


# ═══════════════════════════════════════════════════════════════
# 파일 탐색
# ═══════════════════════════════════════════════════════════════


def find_blend_files(filter_path=None):
    """
    변환 대상 .blend 파일 목록을 반환.
    이미 성공한 파일은 스킵.
    """
    targets = []

    for root, dirs, files in os.walk(ASSET_ROOT):
        # .blend1 등 불필요한 파일 제외
        blend_files = [f for f in files if f.endswith(".blend") and not f.endswith(".blend1")]
        if not blend_files:
            continue

        # 상대 경로 계산
        rel_root = os.path.relpath(root, ASSET_ROOT).replace("\\", "/")

        # 스킵 패턴 체크
        skip = False
        for pat in SKIP_PATTERNS:
            if pat in rel_root or any(pat in f for f in blend_files):
                skip = True
                break

        # 필터 적용
        if filter_path and not rel_root.startswith(filter_path.replace("\\", "/")):
            continue

        if skip:
            continue

        # 프로필 결정
        top_dir = rel_root.split("/")[0]
        profile = PROFILE_MAP.get(top_dir)
        if profile is None:
            continue  # 매핑 없는 디렉토리는 스킵

        for fname in blend_files:
            full_path = os.path.join(root, fname)

            # 이미 성공한 파일 스킵
            result_path = os.path.join(root, "conversion_result.json")
            if os.path.exists(result_path):
                try:
                    with open(result_path, encoding="utf-8") as f:
                        result = json.load(f)
                    if result.get("success"):
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass

            targets.append(
                {
                    "path": full_path,
                    "rel_path": f"{rel_root}/{fname}",
                    "profile": profile,
                    "dir": root,
                }
            )

    return targets


# ═══════════════════════════════════════════════════════════════
# 단일 파일 변환
# ═══════════════════════════════════════════════════════════════


def convert_file(target, timeout=DEFAULT_TIMEOUT, auto_mode=False):
    """
    단일 .blend 파일을 Blender 서브프로세스로 변환.
    Returns: (rel_path, success, message, elapsed)
    """
    path = target["path"]
    profile = target["profile"]
    rel_path = target["rel_path"]

    cmd = [
        BLENDER_EXE,
        "--background",
        path,
        "--python",
        PIPELINE_SCRIPT,
        "--",
    ]

    if auto_mode:
        cmd.append("--auto")
    else:
        cmd.extend(["--profile", profile, "--bmap", profile])

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
        )
        elapsed = time.time() - start

        # 결과 확인
        result_path = os.path.join(target["dir"], "conversion_result.json")
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)
            if result.get("success"):
                return (rel_path, True, "성공", elapsed)
            else:
                errors = result.get("errors", [])
                msg = errors[0] if errors else "알 수 없는 오류"
                return (rel_path, False, msg, elapsed)
        else:
            # 결과 파일이 없으면 stdout에서 에러 추출
            stderr = proc.stderr[-500:] if proc.stderr else ""
            return (rel_path, False, f"결과 파일 미생성. returncode={proc.returncode}", elapsed)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return (rel_path, False, f"타임아웃 ({timeout}초)", elapsed)
    except Exception as e:
        elapsed = time.time() - start
        return (rel_path, False, str(e), elapsed)


# ═══════════════════════════════════════════════════════════════
# 리포트 생성
# ═══════════════════════════════════════════════════════════════


def save_report(results, output_path):
    """배치 결과를 JSON으로 저장"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "success": sum(1 for r in results if r[1]),
        "fail": sum(1 for r in results if not r[1]),
        "total_elapsed_sec": round(sum(r[3] for r in results), 1),
        "files": [
            {
                "path": r[0],
                "success": r[1],
                "message": r[2],
                "elapsed_sec": round(r[3], 1),
            }
            for r in results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="ARP 리그 배치 변환")
    parser.add_argument("--run", action="store_true", help="실제 변환 실행 (없으면 dry-run)")
    parser.add_argument("--filter", type=str, default=None, help="디렉토리 필터 (예: normal/fox)")
    parser.add_argument("--workers", type=int, default=1, help="병렬 워커 수 (기본: 1)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="파일당 타임아웃 (초)")
    parser.add_argument(
        "--blender", type=str, default=None, help="Blender 실행 파일 경로 오버라이드"
    )
    parser.add_argument(
        "--auto", action="store_true", help="구조 기반 자동 분석 모드 (프로필 불필요)"
    )
    args = parser.parse_args()

    global BLENDER_EXE
    if args.blender:
        BLENDER_EXE = args.blender

    # Blender 실행 파일 확인
    if not os.path.exists(BLENDER_EXE):
        print(f"[ERROR] Blender를 찾을 수 없습니다: {BLENDER_EXE}")
        print("  --blender 옵션으로 경로를 지정하세요.")
        sys.exit(1)

    # 파이프라인 스크립트 확인
    if not os.path.exists(PIPELINE_SCRIPT):
        print(f"[ERROR] 파이프라인 스크립트 미발견: {PIPELINE_SCRIPT}")
        sys.exit(1)

    # 대상 파일 탐색
    targets = find_blend_files(filter_path=args.filter)

    print("=" * 60)
    print("ARP 배치 변환")
    print(f"  대상 파일: {len(targets)}개")
    print(f"  필터: {args.filter or '없음'}")
    print(f"  워커: {args.workers}")
    print(f"  타임아웃: {args.timeout}초")
    print("=" * 60)

    if not targets:
        print("변환할 파일이 없습니다.")
        return

    # Dry-run: 대상 파일 목록만 출력
    if not args.run:
        print("\n[DRY-RUN] 변환 대상 파일:")
        for i, t in enumerate(targets):
            print(f"  {i + 1:3d}. [{t['profile']}] {t['rel_path']}")
        print("\n실제 변환하려면 --run 옵션을 추가하세요.")
        return

    # 실제 변환 실행
    results = []
    start_total = time.time()

    if args.workers <= 1:
        # 순차 처리
        for i, target in enumerate(targets):
            print(f"\n[{i + 1}/{len(targets)}] {target['rel_path']}")
            result = convert_file(target, timeout=args.timeout, auto_mode=args.auto)
            results.append(result)
            status = "OK" if result[1] else "FAIL"
            print(f"  {status} ({result[3]:.1f}초) {result[2]}")
    else:
        # 병렬 처리
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_map = {}
            for i, target in enumerate(targets):
                future = executor.submit(convert_file, target, args.timeout, args.auto)
                future_map[future] = (i, target)

            for future in as_completed(future_map):
                i, target = future_map[future]
                result = future.result()
                results.append(result)
                status = "OK" if result[1] else "FAIL"
                print(f"  [{i + 1}/{len(targets)}] {status} ({result[3]:.1f}초) {result[0]}")

    # 리포트 저장
    total_elapsed = time.time() - start_total
    report_name = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = os.path.join(PROJECT_ROOT, report_name)
    report = save_report(results, report_path)

    # 요약 출력
    print("\n" + "=" * 60)
    print("배치 변환 완료")
    print(f"  성공: {report['success']}/{report['total']}")
    print(f"  실패: {report['fail']}/{report['total']}")
    print(f"  총 소요시간: {total_elapsed:.1f}초")
    print(f"  리포트: {report_path}")
    print("=" * 60)

    # 실패 파일 목록
    failed = [r for r in results if not r[1]]
    if failed:
        print("\n실패 파일:")
        for r in failed:
            print(f"  {r[0]}: {r[2]}")


if __name__ == "__main__":
    main()
