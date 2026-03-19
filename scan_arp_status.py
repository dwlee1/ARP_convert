"""
scan_arp_status.py -- ARP 리깅 상태 판별 스크립트

모든 .blend 파일을 스캔하여 AutoRig Pro(ARP) 리깅 여부를 판별하고 CSV로 출력합니다.
바이너리 패턴 매칭으로 ARP/Rigify/커스텀 리그를 분류합니다.

사용법:
  python scan_arp_status.py                         # 전체 스캔
  python scan_arp_status.py --dir Asset/BlenderFile  # 특정 폴더만
  python scan_arp_status.py --verbose                # ARP 마커 상세 출력

지원 압축: 비압축, gzip, zstd (zstandard 패키지 필요)
  zstd 미지원 시: pip install zstandard
"""

import os
import re
import csv
import gzip
import sys
import datetime
import argparse

# ── zstd 지원 확인 ──
try:
    import zstandard
    _HAS_ZSTD = True
except ImportError:
    _HAS_ZSTD = False

# ── 설정 ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(ROOT_DIR, "arp_status_report.csv")

# ── 리그 타입 상수 ──
RIG_ARP = "ARP"
RIG_RIGIFY = "Rigify"
RIG_CUSTOM = "커스텀"
RIG_NONE = "리그 없음"
RIG_ERROR = "오류"

# ── ARP 탐지 마커 ──
# ARP 리그 생성 후 나타나는 고유 컨트롤러 본 이름들
ARP_BONE_MARKERS = [
    b'c_pos',               # 위치 컨트롤러
    b'c_traj',              # 궤적 컨트롤러
    b'c_root_master',       # 루트 마스터
    b'c_root.x',            # 루트 (중앙)
    b'c_spine_01.x',        # 척추 01
    b'c_spine_02.x',        # 척추 02
    b'c_neck.x',            # 목
    b'c_skull.x',           # 두개골
    b'c_jaw_mstr.x',        # 턱 마스터
    b'c_thigh_fk.l',        # 허벅지 FK
    b'c_leg_fk.l',          # 다리 FK
    b'c_foot_fk.l',         # 발 FK
    b'c_arm_fk.l',          # 팔 FK
    b'c_forearm_fk.l',      # 전완 FK
    b'c_hand_fk.l',         # 손 FK
]

# ARP 레퍼런스 본 마커 (리그 생성 전이라도 ARP 설정이 있음을 나타냄)
ARP_REF_MARKERS = [
    b'root_ref.x',
    b'spine_01_ref.x',
    b'spine_02_ref.x',
    b'neck_ref.x',
    b'thigh_ref.l',
    b'leg_ref.l',
]

# ARP 커스텀 프로퍼티 마커
ARP_PROP_MARKERS = [
    b'arp_rig_type',
    b'rig_id',
]

# Rigify 접두사 (DEF-, MCH-, ORG- 본이 다수 존재하면 Rigify)
RIGIFY_PREFIXES = [b'DEF-', b'MCH-', b'ORG-']

# 커스텀 리그 감지용 본 이름 패턴
# 이 본 이름들이 2개 이상 존재하면 커스텀 리그가 있는 것으로 판단
# (SDNA 블록의 'Armature' 타입명은 모든 .blend에 존재하므로 사용 불가)
CUSTOM_RIG_BONE_MARKERS = [
    # 다리 (L/R, .L/.R 양쪽 표기)
    b'thigh_L',        b'thigh_R',
    b'thigh.L',        b'thigh.R',
    b'leg_L',          b'leg_R',
    b'leg.L',          b'leg.R',
    b'foot_L',         b'foot_R',
    b'foot.L',         b'foot.R',
    # 팔/어깨
    b'shoulder_L',     b'shoulder_R',
    b'shoulder.L',     b'shoulder.R',
    b'upperarm_L',     b'upperarm_R',
    b'upperarm.L',     b'upperarm.R',
    b'hand_L',         b'hand_R',
    b'hand.L',         b'hand.R',
    b'forearm_L',      b'forearm_R',
    b'forearm.L',      b'forearm.R',
    # 몸통/머리/꼬리
    b'hips\x00',       b'Hips\x00',
    b'spine_01',       b'spine_02',
    b'tail_01',        b'tail_02',
    b'tail_1\x00',     b'tail_2\x00',
    b'jaw\x00',        b'Jaw\x00',
]

# ── .blend 압축 형식 ──
BLEND_MAGIC = b'BLENDER'
GZIP_MAGIC = b'\x1f\x8b'
ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'

# ── 파일 용도/버전 토큰 ──
# 이 단어로 시작하는 토큰은 동물명이 아닌 접미사로 판단하여 제거
FILE_PURPOSE_TOKENS = {
    # 파일 용도
    'allani', 'animation', 'anination',  'ani', 'anim',
    'rig', 'modeling', 'model',
    'statue', 'final', 'props',
    'ex', 'test', 'backup', 'old', 'new', 'copy',
    # 애니메이션 액션
    'idle', 'walk', 'run', 'sit', 'sleep', 'stand',
    'jump', 'look', 'swim', 'wash', 'shake', 'trot',
    'hunt', 'eat', 'fly', 'land', 'pose', 'turn',
    'down', 'up', 'zero', 'special', 'attack', 'skill',
    'bark', 'howl', 'dig', 'drink', 'play', 'stretch',
    'yawn', 'scratch', 'death', 'happy', 'angry', 'sad',
    'interact', 'glide', 'flap', 'dive', 'roll', 'growl',
    'sniff', 'wag', 'peck', 'hop', 'crawl', 'sprint',
}


def guess_animal_name(filename):
    """
    파일명에서 동물명 추정.
    용도/버전 관련 접미사(AllAni, animation, statue, final, rig 등)를 제거하고
    순수 동물명만 추출. 같은 동물의 여러 파일이 동일한 이름으로 그룹핑됨.

    예:
      Fox_AllAni_240311.blend  -> fox
      Fox_statue.blend         -> fox
      Fox_final.blend          -> fox
      Baby_Bear_animation.blend -> baby_bear
      cat_gray_06.blend        -> cat_gray
      3082_duck_AllAni.blend   -> duck
    """
    name = os.path.splitext(filename)[0]
    # 숫자 접두사 제거 (3082_duck -> duck)
    name = re.sub(r'^\d{3,4}_', '', name)
    # 괄호 내용 제거 (cat_gray_06(1121추가ani) -> cat_gray_06)
    name = re.sub(r'\(.*?\)', '', name)
    # 언더스코어/공백으로 분할
    tokens = re.split(r'[_ ]+', name)
    # 동물명 토큰 추출 (용도/버전 토큰 이전까지)
    result = []
    for token in tokens:
        t = token.strip()
        if not t:
            continue
        lower = t.lower()
        # 순수 숫자면 중단 (날짜 접미사, 버전 번호)
        if re.match(r'^\d+$', lower):
            break
        # 용도 토큰으로 시작하면 중단
        if any(lower.startswith(stop) for stop in FILE_PURPOSE_TOKENS):
            break
        result.append(lower)

    return '_'.join(result).strip('_') if result else os.path.splitext(filename)[0].lower()


def format_size(size_bytes):
    """파일 크기 포맷"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_top_folder(rel_path):
    """상대 경로에서 최상위 폴더명 추출"""
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) > 1:
        # Asset/BlenderFile/normal/... -> normal
        # 2단계 이상이면 BlenderFile 하위 폴더를 추출
        if parts[0] == 'Asset' and len(parts) > 2:
            return parts[2] if parts[1] == 'BlenderFile' else parts[1]
        return parts[0]
    return "(root)"


def detect_compression(filepath):
    """Blend 파일의 압축 형식 감지"""
    try:
        with open(filepath, 'rb') as f:
            magic = f.read(7)
        if magic[:7] == BLEND_MAGIC:
            return 'none'
        elif magic[:2] == GZIP_MAGIC:
            return 'gzip'
        elif magic[:4] == ZSTD_MAGIC:
            return 'zstd'
        return 'unknown'
    except Exception:
        return 'error'


def read_blend_data(filepath):
    """
    Blend 파일 바이트 읽기 (압축 자동 처리).

    Returns:
        bytes | None: 파일 데이터 또는 None (읽기 실패)
        str: 압축 형식 ('none', 'gzip', 'zstd', 'unknown', 'error')
    """
    comp = detect_compression(filepath)

    try:
        if comp == 'none':
            with open(filepath, 'rb') as f:
                return f.read(), comp
        elif comp == 'gzip':
            with gzip.open(filepath, 'rb') as f:
                return f.read(), comp
        elif comp == 'zstd':
            if _HAS_ZSTD:
                with open(filepath, 'rb') as f:
                    dctx = zstandard.ZstdDecompressor()
                    # max_output_size: 500MB 제한
                    return dctx.decompress(f.read(), max_output_size=500 * 1024 * 1024), comp
            else:
                return None, comp
        else:
            return None, comp
    except Exception:
        return None, 'error'


def detect_rig_type(filepath):
    """
    .blend 파일의 리그 타입을 바이너리 패턴으로 판별.

    Returns:
        (rig_type, details_dict)
    """
    data, compression = read_blend_data(filepath)

    if data is None:
        error_msg = '파일 읽기 실패'
        if compression == 'zstd' and not _HAS_ZSTD:
            error_msg = 'zstd 압축 (pip install zstandard 필요)'
        return RIG_ERROR, {
            'error': error_msg,
            'compression': compression,
            'arp_bones': [],
            'arp_refs': [],
            'arp_props': [],
            'arp_bone_count': 0,
            'arp_ref_count': 0,
            'rigify_count': 0,
            'has_armature': False,
        }

    # ARP 컨트롤러 본 마커 검색
    arp_bone_hits = []
    for marker in ARP_BONE_MARKERS:
        if marker in data:
            arp_bone_hits.append(marker.decode('utf-8', errors='replace'))

    # ARP 레퍼런스 본 마커 검색
    arp_ref_hits = []
    for marker in ARP_REF_MARKERS:
        if marker in data:
            arp_ref_hits.append(marker.decode('utf-8', errors='replace'))

    # ARP 프로퍼티 마커 검색
    arp_prop_hits = []
    for marker in ARP_PROP_MARKERS:
        if marker in data:
            arp_prop_hits.append(marker.decode('utf-8', errors='replace'))

    # Rigify 마커 검색
    rigify_total = 0
    for prefix in RIGIFY_PREFIXES:
        rigify_total += data.count(prefix)

    # 커스텀 리그 본 마커 검색
    custom_bone_hits = 0
    for marker in CUSTOM_RIG_BONE_MARKERS:
        if marker in data:
            custom_bone_hits += 1

    # 본 이름 기반으로 아마추어 존재 판단
    # (SDNA의 'Armature' 타입명은 모든 파일에 존재하므로 사용 불가)
    has_armature = custom_bone_hits >= 2

    details = {
        'compression': compression,
        'arp_bones': arp_bone_hits,
        'arp_refs': arp_ref_hits,
        'arp_props': arp_prop_hits,
        'arp_bone_count': len(arp_bone_hits),
        'arp_ref_count': len(arp_ref_hits),
        'rigify_count': rigify_total,
        'custom_bone_hits': custom_bone_hits,
        'has_armature': has_armature,
    }

    # 판별 로직
    # ARP: 컨트롤러 본 2개 이상, 또는 컨트롤러 1개 + 프로퍼티 1개
    if len(arp_bone_hits) >= 2:
        return RIG_ARP, details
    if len(arp_bone_hits) >= 1 and len(arp_prop_hits) >= 1:
        return RIG_ARP, details
    # ARP 레퍼런스만 있는 경우 (설정 중이지만 아직 미생성)
    if len(arp_ref_hits) >= 3:
        return RIG_ARP, details

    # Rigify: DEF-/MCH-/ORG- 접두사 본이 다수
    if rigify_total >= 15:
        return RIG_RIGIFY, details

    # 아마추어 있지만 ARP/Rigify 아님 -> 커스텀
    if has_armature:
        return RIG_CUSTOM, details

    # 아마추어 없음
    return RIG_NONE, details


def scan_blend_files(scan_dir):
    """모든 .blend 파일을 수집"""
    blend_files = []
    for dirpath, dirnames, filenames in os.walk(scan_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for filename in filenames:
            if filename.endswith('.blend') and not re.search(r'\.blend\d+$', filename):
                blend_files.append(os.path.join(dirpath, filename))
    return sorted(blend_files)


def scan_all(scan_dir, verbose=False):
    """전체 스캔 실행"""
    blend_files = scan_blend_files(scan_dir)
    total = len(blend_files)

    if total == 0:
        print("  .blend 파일을 찾을 수 없습니다.")
        return []

    print(f"  {total}개 .blend 파일 발견\n")

    results = []
    zstd_skipped = 0

    for i, filepath in enumerate(blend_files, 1):
        filename = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, ROOT_DIR)

        # 진행률
        if i % 10 == 0 or i == total or i == 1:
            pct = i * 100 // total
            sys.stdout.write(f"\r  [{pct:3d}%] {i}/{total} 스캔 중...")
            sys.stdout.flush()

        # 리그 타입 판별
        rig_type, details = detect_rig_type(filepath)

        if details.get('compression') == 'zstd' and not _HAS_ZSTD:
            zstd_skipped += 1

        # 파일 정보
        stat = os.stat(filepath)
        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)

        result = {
            'filename': filename,
            'rel_path': rel_path.replace('\\', '/'),
            'top_folder': get_top_folder(rel_path.replace('\\', '/')),
            'animal_name': guess_animal_name(filename),
            'rig_type': rig_type,
            'is_arp': 'O' if rig_type == RIG_ARP else 'X',
            'arp_markers': ', '.join(details.get('arp_bones', [])),
            'arp_marker_count': details.get('arp_bone_count', 0),
            'compression': details.get('compression', ''),
            'has_armature': details.get('has_armature', False),
            'mod_date': mod_time.strftime("%Y-%m-%d"),
            'size_bytes': stat.st_size,
            'size_display': format_size(stat.st_size),
        }
        results.append(result)

        if verbose and rig_type == RIG_ARP:
            print(f"\n    ARP: {filename}")
            print(f"      본: {', '.join(details.get('arp_bones', []))}")
            if details.get('arp_refs'):
                print(f"      ref: {', '.join(details['arp_refs'])}")

    sys.stdout.write(f"\r  [100%] {total}/{total} 스캔 완료       \n")

    if zstd_skipped > 0:
        print(f"\n  [!] zstd 압축 파일 {zstd_skipped}개 스킵됨")
        print(f"    -> pip install zstandard 설치 후 재실행하세요")

    return results


def mark_duplicates(results):
    """
    동물명 기준으로 중복 파일을 판별.
    같은 동물명의 파일 중 가장 최신 수정일인 파일만 '사용중', 나머지는 '이전 버전'.
    """
    # 동물명별 그룹핑
    groups = {}
    for r in results:
        key = r['animal_name']
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    for key, group in groups.items():
        if len(group) == 1:
            group[0]['status'] = '사용중'
            group[0]['dup_count'] = 1
            continue

        # 수정일(size_bytes를 기준으로 최신 파일 결정은 부정확, mod timestamp 사용)
        # size_bytes 순이 아닌 수정일 기준
        latest = max(group, key=lambda r: r['size_bytes'])
        # 실제로는 수정일 기준이 더 정확 -- mod_date 문자열 비교
        latest = max(group, key=lambda r: r['mod_date'])

        for r in group:
            if r is latest:
                r['status'] = '사용중'
            else:
                r['status'] = '이전 버전'
            r['dup_count'] = len(group)


def write_csv(results):
    """CSV 출력"""
    fieldnames = [
        'animal_name', 'filename', 'status', 'is_arp', 'rig_type',
        'arp_markers', 'arp_marker_count', 'dup_count', 'top_folder',
        'rel_path', 'mod_date', 'size_display',
    ]
    headers = {
        'animal_name': '동물명(추정)',
        'filename': '파일명',
        'status': '사용 상태',
        'is_arp': 'ARP 여부',
        'rig_type': '리그 타입',
        'arp_markers': 'ARP 마커',
        'arp_marker_count': 'ARP 마커 수',
        'dup_count': '동명 파일 수',
        'top_folder': '폴더',
        'rel_path': '경로',
        'mod_date': '수정일',
        'size_display': '파일 크기',
    }

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([headers[k] for k in fieldnames])
        for r in results:
            writer.writerow([r[k] for k in fieldnames])

    return OUTPUT_CSV


def print_summary(results):
    """콘솔 요약 출력"""
    total = len(results)
    if total == 0:
        return

    active = [r for r in results if r['status'] == '사용중']
    old = [r for r in results if r['status'] == '이전 버전']
    active_total = len(active)

    print(f"\n{'=' * 60}")
    print(f"  ARP 리깅 상태 스캔 결과")
    print(f"{'=' * 60}")
    print(f"\n  총 파일: {total}개 (사용중 {active_total} + 이전 버전 {len(old)})")

    # ── 사용중 파일 기준 통계 ──
    by_type = {}
    for r in active:
        t = r['rig_type']
        by_type[t] = by_type.get(t, 0) + 1

    arp_count = by_type.get(RIG_ARP, 0)
    custom_count = by_type.get(RIG_CUSTOM, 0)
    none_count = by_type.get(RIG_NONE, 0)

    print(f"\n  [사용중 파일 기준] ({active_total}개)")
    type_order = [RIG_ARP, RIG_RIGIFY, RIG_CUSTOM, RIG_NONE, RIG_ERROR]
    for t in type_order:
        count = by_type.get(t, 0)
        if count > 0:
            pct = count * 100 / active_total
            bar_len = int(pct / 2)
            bar = '#' * bar_len
            print(f"    {t:10s}: {count:4d}개 ({pct:5.1f}%) {bar}")

    if custom_count + arp_count > 0:
        rig_total = arp_count + custom_count
        print(f"\n  ARP 변환률 (리그 파일 기준): {arp_count}/{rig_total} ({arp_count * 100 / rig_total:.1f}%)")
        print(f"  변환 필요: {custom_count}개 (커스텀 리그)")

    # ── 폴더별 현황 (사용중만) ──
    folder_stats = {}
    for r in active:
        folder = r['top_folder']
        if folder not in folder_stats:
            folder_stats[folder] = {'total': 0, 'arp': 0, 'custom': 0, 'none': 0}
        folder_stats[folder]['total'] += 1
        if r['rig_type'] == RIG_ARP:
            folder_stats[folder]['arp'] += 1
        elif r['rig_type'] == RIG_CUSTOM:
            folder_stats[folder]['custom'] += 1
        elif r['rig_type'] == RIG_NONE:
            folder_stats[folder]['none'] += 1

    print(f"\n  폴더별 현황 (사용중 파일):")
    print(f"    {'폴더':20s} {'전체':>5s} {'ARP':>5s} {'커스텀':>6s} {'없음':>5s} {'ARP%':>6s}")
    print(f"    {'-' * 50}")
    for folder in sorted(folder_stats.keys()):
        s = folder_stats[folder]
        rig_total = s['arp'] + s['custom']
        pct = s['arp'] * 100 / rig_total if rig_total else 0
        print(f"    {folder:20s} {s['total']:5d} {s['arp']:5d} {s['custom']:6d} {s['none']:5d} {pct:5.1f}%")

    # ── 중복 통계 ──
    dup_animals = sum(1 for r in active if r['dup_count'] > 1)
    print(f"\n  중복 파일: {len(old)}개 (이전 버전, {dup_animals}개 동물)")

    print(f"\n  CSV 저장: {OUTPUT_CSV}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description='ARP 리깅 상태 스캔')
    parser.add_argument('--dir', default=ROOT_DIR, help='스캔 디렉토리 (기본: 프로젝트 루트)')
    parser.add_argument('--verbose', '-v', action='store_true', help='ARP 마커 상세 출력')
    parser.add_argument('--latest-only', action='store_true', help='사용중 파일만 CSV에 출력')
    args = parser.parse_args()

    scan_dir = os.path.abspath(args.dir)

    print(f"{'=' * 60}")
    print(f"  ARP 리깅 상태 스캔")
    print(f"{'=' * 60}")
    print(f"  디렉토리: {scan_dir}")
    if not _HAS_ZSTD:
        print(f"  [!] zstandard 미설치 -- zstd 압축 파일은 스킵됩니다")
        print(f"    설치: pip install zstandard")
    print()

    results = scan_all(scan_dir, verbose=args.verbose)

    if not results:
        return

    # 중복 파일 판별
    mark_duplicates(results)

    # 정렬: 사용상태 -> 리그타입 -> 폴더 -> 동물명
    status_order = {'사용중': 0, '이전 버전': 1}
    type_order = {RIG_ARP: 0, RIG_RIGIFY: 1, RIG_CUSTOM: 2, RIG_NONE: 3, RIG_ERROR: 4}
    results.sort(key=lambda r: (
        status_order.get(r['status'], 9),
        type_order.get(r['rig_type'], 9),
        r['top_folder'],
        r['animal_name'],
    ))

    # --latest-only: 사용중 파일만 출력
    csv_results = results
    if args.latest_only:
        csv_results = [r for r in results if r['status'] == '사용중']

    write_csv(csv_results)
    print_summary(results)


if __name__ == '__main__':
    main()
