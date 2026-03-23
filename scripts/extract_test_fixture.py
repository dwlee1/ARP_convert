"""
테스트 fixture 추출 스크립트
============================
Blender에서 실행하여 소스 아마추어의 bone data를 JSON으로 저장.
저장된 JSON은 pytest에서 Blender 없이 분석 로직을 테스트하는 데 사용.

사용법 (Blender 내부):
  1. 소스 아마추어를 선택
  2. Scripting 탭에서 이 스크립트 실행

사용법 (커맨드라인):
  blender --background file.blend --python scripts/extract_test_fixture.py -- animal_name

출력:
  tests/fixtures/<name>.json
"""

import bpy
import json
import os
import sys


def extract_all_bone_data(armature_obj):
    """
    아마추어에서 모든 본의 데이터를 추출 (skeleton_analyzer.extract_bone_data와 동일 로직).
    """
    if bpy.context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass

    try:
        bpy.ops.object.select_all(action='DESELECT')
    except RuntimeError:
        pass

    armature_obj.hide_set(False)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

    world_matrix = armature_obj.matrix_world
    bones = {}

    for ebone in armature_obj.data.edit_bones:
        head_world = world_matrix @ ebone.head.copy()
        tail_world = world_matrix @ ebone.tail.copy()

        head_t = [head_world.x, head_world.y, head_world.z]
        tail_t = [tail_world.x, tail_world.y, tail_world.z]

        dx = tail_t[0] - head_t[0]
        dy = tail_t[1] - head_t[1]
        dz = tail_t[2] - head_t[2]
        import math
        length = math.sqrt(dx*dx + dy*dy + dz*dz)
        if length > 1e-8:
            direction = [dx/length, dy/length, dz/length]
        else:
            direction = [0, 0, 0]

        bones[ebone.name] = {
            'name': ebone.name,
            'head': head_t,
            'tail': tail_t,
            'roll': ebone.roll,
            'parent': ebone.parent.name if ebone.parent else None,
            'children': [c.name for c in ebone.children],
            'is_deform': ebone.use_deform,
            'direction': direction,
            'length': length,
            'use_connect': ebone.use_connect,
        }

    bpy.ops.object.mode_set(mode='OBJECT')
    return bones


def save_fixture(armature_obj, name, output_dir):
    """bone data를 JSON fixture로 저장."""
    all_bones = extract_all_bone_data(armature_obj)

    fixture = {
        'name': name,
        'source_armature': armature_obj.name,
        'bone_count': len(all_bones),
        'deform_count': sum(1 for b in all_bones.values() if b['is_deform']),
        'all_bones': all_bones,
    }

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.json")

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)

    print(f"[Fixture] 저장 완료: {path}")
    print(f"  전체 본: {fixture['bone_count']}, deform 본: {fixture['deform_count']}")
    return path


def main():
    # 커맨드라인 인수에서 이름 추출
    argv = sys.argv
    name = None
    if '--' in argv:
        args_after = argv[argv.index('--') + 1:]
        if args_after:
            name = args_after[0]

    # 프로젝트 루트: .git 폴더를 찾아 올라가거나, 고정 경로 사용
    def _find_project_root():
        # 방법 1: 스크립트 위치 기준
        candidates = []
        try:
            candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        except Exception:
            pass
        # 방법 2: 고정 경로
        candidates.append(r"C:\Users\manag\Desktop\BlenderRigConvert")
        for c in candidates:
            if os.path.exists(os.path.join(c, 'CLAUDE.md')):
                return c
        return candidates[-1]

    project_root = _find_project_root()
    output_dir = os.path.join(project_root, 'tests', 'fixtures')

    # 활성 아마추어 또는 첫 번째 아마추어 사용
    armature_obj = None
    active = bpy.context.view_layer.objects.active
    if active and active.type == 'ARMATURE':
        armature_obj = active
    else:
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                armature_obj = obj
                break

    if armature_obj is None:
        print("[Fixture] 오류: 아마추어를 찾을 수 없습니다.")
        return

    if name is None:
        # blend 파일 이름에서 추출
        blend_name = os.path.basename(bpy.data.filepath)
        name = os.path.splitext(blend_name)[0] if blend_name else armature_obj.name

    save_fixture(armature_obj, name, output_dir)


if __name__ == '__main__':
    main()
