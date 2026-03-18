"""
cleanup_blend1.py — .blend1 자동 백업 파일 삭제 스크립트

블렌더가 자동으로 생성하는 .blend1 백업 파일을 찾아서 삭제합니다.
- 삭제 전 목록과 총 용량을 출력
- 사용자 확인 후 삭제 진행
- 삭제 결과 로그 출력
"""

import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def format_size(size_bytes):
    """파일 크기를 읽기 좋은 형태로 변환"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def find_blend_backups():
    """모든 .blend1, .blend2 등 백업 파일을 찾기"""
    backups = []

    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        for filename in filenames:
            # .blend1, .blend2 등 매칭
            if re.search(r'\.blend\d+$', filename):
                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, ROOT_DIR)
                size = os.path.getsize(filepath)
                backups.append({
                    'filepath': filepath,
                    'rel_path': rel_path.replace('\\', '/'),
                    'size': size,
                })

    backups.sort(key=lambda f: f['rel_path'])
    return backups


def print_summary(backups):
    """삭제 대상 요약 출력"""
    total_size = sum(b['size'] for b in backups)

    # 폴더별 집계
    by_folder = {}
    for b in backups:
        folder = b['rel_path'].split('/')[0]
        if folder not in by_folder:
            by_folder[folder] = {'count': 0, 'size': 0}
        by_folder[folder]['count'] += 1
        by_folder[folder]['size'] += b['size']

    print("=" * 60)
    print("  .blend1 백업 파일 삭제 스크립트")
    print("=" * 60)
    print(f"\n  발견된 백업 파일: {len(backups)}개")
    print(f"  총 용량: {format_size(total_size)}")
    print(f"\n  폴더별 현황:")

    for folder, info in sorted(by_folder.items()):
        print(f"    {folder}: {info['count']}개 ({format_size(info['size'])})")

    print()


def delete_files(backups):
    """파일 삭제 실행"""
    deleted = 0
    failed = 0
    freed = 0

    for b in backups:
        try:
            os.remove(b['filepath'])
            deleted += 1
            freed += b['size']
        except OSError as e:
            print(f"  [실패] {b['rel_path']}: {e}")
            failed += 1

    print(f"\n  삭제 완료: {deleted}개 ({format_size(freed)} 확보)")
    if failed:
        print(f"  삭제 실패: {failed}개")
    print("=" * 60)


if __name__ == '__main__':
    print(".blend1 백업 파일 검색 중...")
    backups = find_blend_backups()

    if not backups:
        print("삭제할 .blend1 백업 파일이 없습니다.")
        sys.exit(0)

    print_summary(backups)

    # --yes 옵션으로 확인 건너뛰기
    if '--yes' in sys.argv:
        confirm = 'y'
    else:
        confirm = input("  위 파일들을 모두 삭제하시겠습니까? (y/N): ").strip().lower()

    if confirm == 'y':
        print("\n  삭제 진행 중...")
        delete_files(backups)
    else:
        print("\n  삭제를 취소했습니다.")
