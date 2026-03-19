"""
리그 구조 조사 스크립트
========================
현재 열린 .blend 파일의 아마추어와 본 구조를 출력합니다.
Blender Scripting 탭에서 실행하세요.
"""

import bpy
import os

print("=" * 60)
print("리그 구조 조사")
print(f"파일: {bpy.data.filepath}")
print("=" * 60)

# 모든 아마추어 오브젝트 조사
armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
print(f"\n아마추어 오브젝트: {len(armatures)}개")

for arm_obj in armatures:
    arm = arm_obj.data
    bones = arm.bones
    print(f"\n{'─' * 50}")
    print(f"아마추어: '{arm_obj.name}' (data: '{arm.name}')")
    print(f"  총 본 수: {len(bones)}")

    # 접두사별 분류
    prefixes = {}
    for bone in bones:
        prefix = bone.name.split("-")[0] if "-" in bone.name else bone.name.split("_")[0] if "_" in bone.name else bone.name.split(".")[0]
        prefixes[prefix] = prefixes.get(prefix, 0) + 1

    print(f"  접두사별 분류:")
    for prefix, count in sorted(prefixes.items(), key=lambda x: -x[1]):
        print(f"    {prefix}: {count}개")

    # 첫 30개 본 이름 출력
    print(f"  본 이름 (처음 30개):")
    for i, bone in enumerate(bones):
        if i >= 30:
            print(f"    ... 외 {len(bones) - 30}개")
            break
        parent_name = bone.parent.name if bone.parent else "(루트)"
        print(f"    {bone.name}  ← {parent_name}")

    # DEF 본 확인
    def_bones = [b for b in bones if b.name.startswith('DEF-')]
    print(f"\n  DEF- 본: {len(def_bones)}개")
    if def_bones:
        for b in def_bones[:10]:
            print(f"    {b.name}")

    # c_ 본 확인 (ARP)
    c_bones = [b for b in bones if b.name.startswith('c_')]
    print(f"  c_ 본 (ARP): {len(c_bones)}개")
    if c_bones:
        for b in c_bones[:10]:
            print(f"    {b.name}")

# 메시 오브젝트와 아마추어 모디파이어 확인
print(f"\n{'─' * 50}")
print("메시-아마추어 연결:")
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                print(f"  메시 '{obj.name}' → 아마추어 '{mod.object.name if mod.object else '(없음)'}'")

# 액션 확인
print(f"\n{'─' * 50}")
print(f"액션: {len(bpy.data.actions)}개")
for action in bpy.data.actions:
    fc_count = len(action.fcurves)
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])
    print(f"  '{action.name}' — fcurves: {fc_count}, 프레임: {frame_start}~{frame_end}")

# 파일로 저장
output_path = os.path.join(os.path.dirname(bpy.data.filepath), "rig_inspection.txt")
# 콘솔 출력을 캡처하지는 않지만 안내
print(f"\n{'=' * 60}")
print("위 내용을 복사해서 공유해주세요.")
print(f"{'=' * 60}")
