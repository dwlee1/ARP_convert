"""
ARP 리타겟 설정/정리 유틸리티
============================
bone_pairs 직렬화, 리타겟 씬 프로퍼티 세팅, bones_map_v2 오버라이드,
베이크 후 정리(소스 삭제, 액션 rename) 등 리타게팅 관련 로직을 모은다.

arp_utils에서 분리됨. 공통 함수(log, ensure_object_mode 등)는
arp_utils에서 late import로 가져온다.

Consumes: bpy scene state, bone_pairs
Produces: retarget setup, cleanup
"""

import json
import re

import bpy

__all__ = [
    "BAKE_PAIRS_KEY",
    "_POLE_CTRL_PATTERN",
    "_classify_ctrl",
    "_copy_custom_scale_fcurves",
    "_delete_existing_remap_actions",
    "_mute_tail_master_constraints",
    "_override_bones_map",
    "cleanup_after_retarget",
    "deserialize_bone_pairs",
    "preflight_check_transforms",
    "serialize_bone_pairs",
    "setup_arp_retarget",
]

# ── 상수 ──

BAKE_PAIRS_KEY = "arpconv_bone_pairs"

# Pole vector 패턴 (pole_parent=1로 처리, 매핑 제외)
_POLE_CTRL_PATTERN = re.compile(r"^c_(leg|arm)_pole")


# ═══════════════════════════════════════════════════════════════
# 직렬화
# ═══════════════════════════════════════════════════════════════


def serialize_bone_pairs(pairs):
    """bone_pairs 리스트를 JSON 문자열로 직렬화.

    Args:
        pairs: [(source_bone, arp_controller, is_custom), ...]

    Returns:
        str: JSON 문자열
    """
    return json.dumps([list(t) for t in pairs], ensure_ascii=False)


def deserialize_bone_pairs(json_str):
    """JSON 문자열에서 bone_pairs 리스트 복원.

    Returns:
        list[tuple]: [(source_bone, arp_controller, is_custom), ...]
    """
    raw = json.loads(json_str)
    return [(r[0], r[1], r[2]) for r in raw]


# ═══════════════════════════════════════════════════════════════
# 프리플라이트
# ═══════════════════════════════════════════════════════════════


def preflight_check_transforms(source_obj, arp_obj):
    """베이크 전 오브젝트 transform 검증. 실패 시 에러 메시지 반환.

    Returns:
        str or None: 에러 메시지 (None이면 통과)
    """
    from mathutils import Vector

    tolerance = 1e-4
    for obj, label in [(source_obj, "소스"), (arp_obj, "ARP")]:
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        if (loc - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 위치가 원점이 아닙니다: {tuple(round(v, 4) for v in loc)}"
        if (Vector(rot) - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 회전이 0이 아닙니다: {tuple(round(v, 4) for v in rot)}"
        if (scale - Vector((1, 1, 1))).length > tolerance:
            return f"{label} 아마추어 스케일이 1이 아닙니다: {tuple(round(v, 4) for v in scale)}"
    return None


# ═══════════════════════════════════════════════════════════════
# 내부 헬퍼
# ═══════════════════════════════════════════════════════════════


def _classify_ctrl(ctrl_name, is_custom):
    """컨트롤러 이름에서 ARP 리타겟 플래그를 결정한다.

    ik=True는 월드 스페이스 매칭으로, rest-pose 차이와 무관하게 정확한 위치/회전을
    보장한다. root만 location=True로 유지 (set_as_root 필요).

    Returns:
        dict: {"location": bool, "ik": bool, "set_as_root": bool, "ctrl": str}
    """
    # root: c_root_master.x → c_root.x로 교체, set_as_root=True
    if ctrl_name == "c_root_master.x":
        return {"ctrl": "c_root.x", "location": True, "ik": False, "set_as_root": True}

    # root 외 모든 본: ik=True (월드 스페이스 매칭)
    return {"ctrl": ctrl_name, "location": False, "ik": True, "set_as_root": False}


def _override_bones_map(bone_pairs):
    """bone_pairs 기반으로 ARP bones_map_v2 엔트리를 오버라이드.

    bone_pairs에 매핑이 있는 본은 우리 매핑으로 덮어쓰고,
    bone_pairs에 없는 본은 빈 매핑("")으로 비운다.
    사용자가 필요하면 ARP Remap UI에서 수동 추가 가능.
    """
    from arp_utils import log

    scn = bpy.context.scene

    # bone_pairs → 룩업 테이블 (src_name → 매핑 정보)
    # pole vector 본은 제외 (pole_parent=1로 ARP가 자동 처리)
    lookup = {}
    for src_name, ctrl_name, is_custom in bone_pairs:
        if _POLE_CTRL_PATTERN.match(ctrl_name):
            continue
        classified = _classify_ctrl(ctrl_name, is_custom)
        lookup[src_name] = classified

    overridden = 0
    cleared = 0
    for entry in scn.bones_map_v2:
        if entry.source_bone in lookup:
            info = lookup[entry.source_bone]
            entry.name = info["ctrl"]
            entry.location = info["location"]
            entry.ik = info["ik"]
            entry.set_as_root = info["set_as_root"]
            overridden += 1
        elif entry.name:
            # bone_pairs에 없는 본: ARP 자동 추측 제거
            entry.name = ""
            entry.location = False
            entry.ik = False
            entry.set_as_root = False
            cleared += 1

    log(f"  bones_map_v2 오버라이드: {overridden}/{len(lookup)}개, 추측 제거: {cleared}개")
    if overridden < len(lookup):
        missing = set(lookup.keys()) - {e.source_bone for e in scn.bones_map_v2}
        if missing:
            log(f"  bones_map_v2에 없는 소스 본: {missing}", "WARN")


def _mute_tail_master_constraints(arp_obj):
    """tail controller의 COPY_ROTATION(tail_master) constraint를 mute.

    ARP tail 시스템은 c_tail_master.x의 회전을 OFFSET 모드로 각 tail controller에
    더하는 구조다. 리타겟 시 이 constraint가 활성화되어 있으면 리타겟 회전에
    추가 회전이 합산되어 오차가 체인을 따라 누적된다.
    """
    from arp_utils import log

    muted = 0
    for pb in arp_obj.pose.bones:
        if not pb.name.startswith("c_tail_"):
            continue
        for c in pb.constraints:
            if c.type == "COPY_ROTATION" and "tail_master" in c.name and not c.mute:
                c.mute = True
                muted += 1
    if muted:
        log(f"  tail_master constraint mute: {muted}개")


def _delete_existing_remap_actions():
    """기존 _remap 액션을 삭제하여 중복 방지."""
    from arp_utils import log

    removed = []
    for action in list(bpy.data.actions):
        if action.name.endswith("_remap") or "_remap." in action.name:
            removed.append(action.name)
            bpy.data.actions.remove(action)
    if removed:
        log(f"  기존 _remap 액션 삭제: {len(removed)}개")


def _copy_custom_scale_fcurves(arp_obj):
    """커스텀 본의 스케일 fcurve를 소스 액션에서 _remap 액션으로 복사.

    ARP 리타겟은 위치/회전만 전송하고 스케일을 무시한다.
    커스텀 본(eye, jaw 등)은 스케일로 형태 변화를 표현하는 경우가 많으므로
    소스 액션의 스케일 키프레임을 remap 액션에 그대로 복사한다.
    """
    from arp_utils import log

    bone_pairs = deserialize_bone_pairs(arp_obj.get(BAKE_PAIRS_KEY, "[]"))
    custom_pairs = [(src, ctrl) for src, ctrl, is_custom in bone_pairs if is_custom]
    if not custom_pairs:
        return 0

    copied = 0
    for action in bpy.data.actions:
        if not action.name.endswith("_remap"):
            continue
        src_action_name = action.name[: -len("_remap")]
        src_action = bpy.data.actions.get(src_action_name)
        if src_action is None:
            continue

        for def_src, target in custom_pairs:
            # DEF- 접두사 제거 → 소스 액션의 원본 본 이름
            original = def_src[4:] if def_src.startswith("DEF-") else def_src
            src_path = f'pose.bones["{original}"].scale'
            tgt_path = f'pose.bones["{target}"].scale'

            for axis in range(3):
                src_fc = src_action.fcurves.find(src_path, index=axis)
                if src_fc is None:
                    continue

                # remap 액션에서 기존 scale fcurve 제거 후 재생성
                tgt_fc = action.fcurves.find(tgt_path, index=axis)
                if tgt_fc:
                    action.fcurves.remove(tgt_fc)
                tgt_fc = action.fcurves.new(tgt_path, index=axis)

                # 키프레임 복사
                for kp in src_fc.keyframe_points:
                    tgt_fc.keyframe_points.insert(kp.co[0], kp.co[1])

                # 보간 모드 복사
                for i, kp in enumerate(tgt_fc.keyframe_points):
                    if i < len(src_fc.keyframe_points):
                        kp.interpolation = src_fc.keyframe_points[i].interpolation
                        kp.handle_left_type = src_fc.keyframe_points[i].handle_left_type
                        kp.handle_right_type = src_fc.keyframe_points[i].handle_right_type

                copied += 1

    if copied:
        log(f"  커스텀 본 스케일 복사: {copied}개 fcurve")
    return copied


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════


def setup_arp_retarget(source_obj, arp_obj, bone_pairs):
    """bone_pairs를 ARP bones_map_v2로 변환하고 리타겟 씬 프로퍼티를 설정한다.

    ARP Remap 패널에서 사용자가 매핑을 확인/수정한 뒤
    ARP Re-Retarget 버튼을 직접 클릭하여 베이크한다.

    Returns:
        dict: {"overridden": int, "total_pairs": int, "remap_deleted": int}
    """
    from arp_utils import ensure_object_mode, log, run_arp_operator, select_only

    scn = bpy.context.scene

    # 1. Scene property 세팅
    scn.source_rig = source_obj.name
    scn.target_rig = arp_obj.name
    log(f"  source_rig={source_obj.name}, target_rig={arp_obj.name}")

    # 2. ARP build_bones_list 호출 → bones_map_v2 생성
    ensure_object_mode()
    select_only(arp_obj)
    run_arp_operator(bpy.ops.arp.build_bones_list)
    log(f"  build_bones_list 완료: {len(scn.bones_map_v2)}개 엔트리")

    # 3. bone_pairs 기반 오버라이드
    _override_bones_map(bone_pairs)

    # 4. tail master constraint mute (COPY_ROTATION OFFSET이 리타겟 회전을 왜곡)
    _mute_tail_master_constraints(arp_obj)

    # 5. batch_retarget 활성화
    scn.batch_retarget = True
    log("  batch_retarget = True")

    # 6. 기존 _remap 액션 삭제
    _delete_existing_remap_actions()

    return {
        "overridden": len(bone_pairs),
        "total_map_entries": len(scn.bones_map_v2),
    }


def cleanup_after_retarget(source_obj, preview_obj):
    """소스/프리뷰 아마추어 삭제 + _remap 액션을 원본 이름으로 rename.

    Returns:
        dict: {"deleted_armatures": list, "renamed_actions": list}
    """
    from arp_utils import find_arp_armature, log

    deleted_armatures = []
    renamed_actions = []

    # 0. 커스텀 본 스케일 fcurve 복사 (소스 삭제 전에 실행)
    arp_obj = find_arp_armature()
    if arp_obj:
        _copy_custom_scale_fcurves(arp_obj)

    # 1. 소스 액션 삭제 (rename 충돌 방지)
    if source_obj and source_obj.type == "ARMATURE":
        source_bone_names = {b.name for b in source_obj.data.bones}
        for action in list(bpy.data.actions):
            if action.name.endswith("_remap") or "_remap." in action.name:
                continue
            for fc in action.fcurves:
                if fc.data_path.startswith("pose.bones["):
                    try:
                        bone_name = fc.data_path.split('"')[1]
                    except IndexError:
                        continue
                    if bone_name in source_bone_names:
                        log(f"  소스 액션 삭제: {action.name}")
                        bpy.data.actions.remove(action)
                        break

    # 2. 소스/프리뷰 아마추어 삭제
    for obj in [source_obj, preview_obj]:
        if obj is None:
            continue
        obj_name = obj.name
        armature_data = obj.data if obj.type == "ARMATURE" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if armature_data and armature_data.users == 0:
            bpy.data.armatures.remove(armature_data)
        deleted_armatures.append(obj_name)
        log(f"  아마추어 삭제: {obj_name}")

    # 3. _remap 액션을 원본 이름으로 rename
    for action in list(bpy.data.actions):
        if action.name.endswith("_remap"):
            original_name = action.name[: -len("_remap")]
            # 이름 충돌 확인
            if bpy.data.actions.get(original_name):
                log(f"  rename 스킵 (충돌): {action.name} → {original_name}", "WARN")
                continue
            old_name = action.name
            action.name = original_name
            renamed_actions.append(f"{old_name} → {original_name}")
            log(f"  액션 rename: {old_name} → {original_name}")

    return {
        "deleted_armatures": deleted_armatures,
        "renamed_actions": renamed_actions,
    }
