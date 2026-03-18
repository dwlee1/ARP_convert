"""
ARP 리타게팅 워크플로우 레퍼런스
===================================
출처: https://github.com/Shimingyi/ARP-Batch-Retargeting 분석 결과

이 파일은 실행용이 아닌 **참조용 문서**입니다.
ARP 오퍼레이터의 정확한 호출 순서, 파라미터, 컨텍스트 요구사항을 정리합니다.
"""

# ═══════════════════════════════════════════════
# 1. ARP 리타게팅 오퍼레이터 호출 순서
# ═══════════════════════════════════════════════
#
# Step 1: 소스/타겟 아마추어 등록 (씬 프로퍼티)
#   bpy.context.scene.source_rig = source_armature.name  # 오브젝트 이름 (str)
#   bpy.context.scene.target_rig = target_armature.name  # 오브젝트 이름 (str)
#
# Step 2: 스케일 맞춤
#   bpy.ops.arp.auto_scale()                    # 파라미터 없음
#
# Step 3: 본 매핑 구축
#   bpy.ops.arp.build_bones_list()              # 파라미터 없음
#
# Step 4: .bmap 프리셋 로드
#   bpy.ops.arp.import_config_preset(preset_name='preset_filename')
#   # preset_name = .bmap 파일명에서 확장자 제거
#
# Step 5: 레스트 포즈 조정 (필요 시)
#   bpy.ops.arp.redefine_rest_pose()            # Pose 모드로 전환됨
#   # ... 본 선택 & 변환 (translate/rotate) ...
#   bpy.ops.arp.save_pose_rest()                # 포즈를 레스트로 저장
#   bpy.ops.object.mode_set(mode='OBJECT')      # 오브젝트 모드로 복귀
#
# Step 6: 리타게팅 실행
#   bpy.ops.arp.retarget(frame_start=N, frame_end=M)
#   # frame_start, frame_end: 정수
#
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# 2. 프레임 범위 결정
# ═══════════════════════════════════════════════
#
# action = source_armature.animation_data.action
# start_frame = int(action.frame_range[0])
# end_frame = int(action.frame_range[1])
#
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# 3. 컨텍스트 요구사항
# ═══════════════════════════════════════════════
#
# - source_rig / target_rig: 씬 프로퍼티 (bpy.context.scene.xxx)
# - auto_scale, build_bones_list: Object 모드
# - redefine_rest_pose 후: Pose 모드 (ARP가 자동 전환)
# - retarget 전: Object 모드 필수
# - 타겟 아마추어가 active object + selected 상태여야 함
#
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# 4. .bmap 파일 형식
# ═══════════════════════════════════════════════
#
# 4줄 단위 반복 구조:
#
# Line 1: <target_bone>%<bool>%<space>%<loc_offset>%<rot_offset>%<scale>%<bool>%<bool>%
# Line 2: <source_bone>
# Line 3: <is_location_bone: True/False>
# Line 4: <bool: True/False>
# (빈 줄)
#
# 예시:
# mixamorig:Hips%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%
# Hips
# True
# False
#
# 필드 설명 (% 구분):
# 1. 타겟 본 이름
# 2. bool (set_as_root)
# 3. 스페이스 모드 (ABSOLUTE)
# 4. 위치 오프셋 (x,y,z)
# 5. 회전 오프셋 (x,y,z)
# 6. 스케일 팩터 (float)
# 7. bool 플래그
# 8. bool 플래그
#
# Line 2: 소스 본 이름
# Line 3: 위치 데이터 포함 여부 (루트만 True)
# Line 4: 추가 플래그 (보통 False)
#
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# 5. 프리셋 파일 위치
# ═══════════════════════════════════════════════
#
# Windows:
#   C:\Users\USERNAME\AppData\Roaming\Blender Foundation\
#   Blender\[version]\config\addons\auto_rig_pro-master\remap_presets\
#
# .bmap 파일을 이 경로에 복사하면 import_config_preset으로 로드 가능
#
# ═══════════════════════════════════════════════
"""
