"""
ARP Rig Convert 애드온
======================
소스 deform 본 → Preview Armature 생성 → 역할 배정/수정 → ARP 리그 생성.

설치:
  Edit > Preferences > Add-ons > Install > 이 파일 선택
  또는 Blender Scripting 탭에서 직접 실행 (Run Script)
"""

bl_info = {
    "name": "ARP Rig Convert",
    "author": "BlenderRigConvert",
    "version": (2, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > ARP Convert",
    "description": "Preview Armature 기반 ARP 리그 변환",
    "category": "Rigging",
}

import bpy
import os
import sys
import traceback
from bpy.props import (
    StringProperty, FloatProperty, IntProperty,
    BoolProperty, EnumProperty, PointerProperty,
)
from bpy.types import PropertyGroup, Operator, Panel


# ═══════════════════════════════════════════════════════════════
# scripts/ 경로 설정
# ═══════════════════════════════════════════════════════════════

def _ensure_scripts_path():
    """scripts/ 폴더를 sys.path에 추가"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "skeleton_analyzer.py")):
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        return script_dir

    if bpy.data.filepath:
        d = os.path.dirname(bpy.data.filepath)
        for _ in range(10):
            candidate = os.path.join(d, "scripts")
            if os.path.exists(os.path.join(candidate, "skeleton_analyzer.py")):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                return candidate
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return ""


def _reload_modules():
    """개발 중 모듈 리로드"""
    import importlib
    for mod_name in ['skeleton_analyzer', 'arp_utils']:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


# ═══════════════════════════════════════════════════════════════
# 역할 드롭다운
# ═══════════════════════════════════════════════════════════════

ROLE_ITEMS = [
    ('root', "Root", "루트 본"),
    ('spine', "Spine", "스파인 체인"),
    ('neck', "Neck", "목"),
    ('head', "Head", "머리"),
    ('back_leg_l', "Back Leg L", "뒷다리 좌"),
    ('back_leg_r', "Back Leg R", "뒷다리 우"),
    ('back_foot_l', "Back Foot L", "뒷발 좌"),
    ('back_foot_r', "Back Foot R", "뒷발 우"),
    ('front_leg_l', "Front Leg L", "앞다리 좌"),
    ('front_leg_r', "Front Leg R", "앞다리 우"),
    ('front_foot_l', "Front Foot L", "앞발 좌"),
    ('front_foot_r', "Front Foot R", "앞발 우"),
    ('ear_l', "Ear L", "귀 좌"),
    ('ear_r', "Ear R", "귀 우"),
    ('tail', "Tail", "꼬리"),
    ('face', "Face (cc_)", "얼굴 커스텀 본 (eye, jaw, mouth, tongue)"),
    ('unmapped', "Unmapped", "미매핑"),
]


# ═══════════════════════════════════════════════════════════════
# 프로퍼티
# ═══════════════════════════════════════════════════════════════

class ARPCONV_Props(PropertyGroup):
    """전역 프로퍼티"""
    preview_armature: StringProperty(name="Preview Armature", default="")
    source_armature: StringProperty(name="소스 Armature", default="")
    is_analyzed: BoolProperty(name="분석 완료", default=False)
    confidence: FloatProperty(name="신뢰도", default=0.0)


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 1 — 분석 + Preview 생성
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_CreatePreview(Operator):
    """소스 deform 본 추출 → Preview Armature 생성"""
    bl_idname = "arp_convert.create_preview"
    bl_label = "리그 분석 + Preview 생성"
    bl_description = "소스 deform 본을 분석하여 역할별 색상이 적용된 Preview Armature를 생성"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                analyze_skeleton, create_preview_armature,
                generate_verification_report,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"skeleton_analyzer 임포트 실패: {e}")
            return {'CANCELLED'}

        # 소스 아마추어 찾기
        source_obj = self._find_source(context)
        if source_obj is None:
            self.report({'ERROR'}, "소스 아마추어를 찾을 수 없습니다.")
            return {'CANCELLED'}

        # 기존 Preview 제거
        props = context.scene.arp_convert_props
        old_preview = bpy.data.objects.get(props.preview_armature)
        if old_preview:
            bpy.data.objects.remove(old_preview, do_unlink=True)

        # Object 모드 확보
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 분석
        analysis = analyze_skeleton(source_obj)
        if 'error' in analysis:
            self.report({'ERROR'}, analysis['error'])
            return {'CANCELLED'}

        # 검증 리포트 출력
        print(generate_verification_report(analysis))

        # Preview Armature 생성
        preview_obj = create_preview_armature(source_obj, analysis)
        if preview_obj is None:
            self.report({'ERROR'}, "Preview Armature 생성 실패")
            return {'CANCELLED'}

        # 프로퍼티 저장
        props.source_armature = source_obj.name
        props.preview_armature = preview_obj.name
        props.is_analyzed = True
        props.confidence = analysis.get('confidence', 0)

        # Preview 선택
        bpy.ops.object.select_all(action='DESELECT')
        preview_obj.select_set(True)
        context.view_layer.objects.active = preview_obj

        self.report({'INFO'},
            f"Preview 생성 완료 (신뢰도: {props.confidence:.0%}). "
            f"본 선택 → 사이드바에서 역할 변경 가능.")
        return {'FINISHED'}

    def _find_source(self, context):
        """소스 아마추어 찾기: 선택된 것 우선, 없으면 자동"""
        if context.active_object and context.active_object.type == 'ARMATURE':
            c_count = len([b for b in context.active_object.data.bones
                          if b.name.startswith('c_')])
            if c_count <= 5 and '_preview' not in context.active_object.name:
                return context.active_object

        best_obj = None
        best_count = 0
        for obj in bpy.data.objects:
            if obj.type != 'ARMATURE':
                continue
            if '_preview' in obj.name:
                continue
            c_count = len([b for b in obj.data.bones if b.name.startswith('c_')])
            if c_count > 5:
                continue
            total = len(obj.data.bones)
            if total > best_count:
                best_count = total
                best_obj = obj
        return best_obj


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: 역할 변경
# ═══════════════════════════════════════════════════════════════

FOOT_ROLES = {'back_foot_l', 'back_foot_r', 'front_foot_l', 'front_foot_r'}
# bank/heel 가이드 본 접미사
GUIDE_SUFFIX_HEEL = "_heel"
GUIDE_SUFFIX_BANK = "_bank"
# 기본 오프셋 (foot 본 head 기준, 로컬 좌표)
HEEL_OFFSET_Z = -0.02    # 바닥 방향
HEEL_OFFSET_Y = -0.01    # 뒤쪽
BANK_OFFSET_X = 0.015    # 좌우


class ARPCONV_OT_SetRole(Operator):
    """선택된 본의 역할을 변경"""
    bl_idname = "arp_convert.set_role"
    bl_label = "역할 설정"
    bl_options = {'REGISTER', 'UNDO'}

    role: EnumProperty(name="역할", items=ROLE_ITEMS)

    def execute(self, context):
        _ensure_scripts_path()
        from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY

        preview_obj = context.active_object
        if not preview_obj or preview_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Preview Armature를 선택하세요.")
            return {'CANCELLED'}

        # 선택된 본에 역할 적용
        changed = 0
        foot_bones = []  # foot 역할로 변경된 본 이름 수집

        if context.mode == 'POSE':
            selected = context.selected_pose_bones
        else:
            selected = []
            for bone in preview_obj.data.bones:
                if bone.select:
                    pbone = preview_obj.pose.bones.get(bone.name)
                    if pbone:
                        selected.append(pbone)

        for pbone in selected:
            pbone[ROLE_PROP_KEY] = self.role
            color = ROLE_COLORS.get(self.role, ROLE_COLORS['unmapped'])
            pbone.color.palette = 'CUSTOM'
            pbone.color.custom.normal = color
            pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
            pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)
            changed += 1

            if self.role in FOOT_ROLES:
                foot_bones.append(pbone.name)

        if changed == 0:
            self.report({'WARNING'}, "본이 선택되지 않았습니다.")
            return {'FINISHED'}

        # foot 역할이면 bank/heel 가이드 본 자동 생성
        if foot_bones:
            guide_count = self._create_foot_guides(
                context, preview_obj, foot_bones, self.role)
            self.report({'INFO'},
                f"{changed}개 본 → {self.role} + 가이드 {guide_count}개 생성")
        else:
            self.report({'INFO'}, f"{changed}개 본 → {self.role}")

        return {'FINISHED'}

    def _create_foot_guides(self, context, preview_obj, foot_bone_names, role):
        """
        foot 역할 본에 대해 heel/bank 가이드 본을 Preview에 자동 생성.
        가이드 본은 foot 본의 head 기준 오프셋 위치에 생성.
        """
        from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY
        from mathutils import Vector

        # 현재 모드 저장 + Edit Mode 진입
        prev_mode = context.mode
        if prev_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        preview_obj.select_set(True)
        context.view_layer.objects.active = preview_obj
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = preview_obj.data.edit_bones
        created = 0

        # 역할에서 side 추출 (back_foot_l → l)
        side = role.rsplit('_', 1)[-1]  # 'l' or 'r'
        # 역할에서 front/back 추출
        prefix = role.rsplit('_', 2)[0]  # 'back_foot' or 'front_foot'
        prefix_short = prefix.replace('_foot', '')  # 'back' or 'front'

        for foot_name in foot_bone_names:
            foot_eb = edit_bones.get(foot_name)
            if foot_eb is None:
                continue

            foot_head = foot_eb.head.copy()

            # --- Heel 가이드 ---
            heel_name = f"{foot_name}{GUIDE_SUFFIX_HEEL}"
            # 기존 가이드 제거 후 재생성
            old_heel = edit_bones.get(heel_name)
            if old_heel:
                edit_bones.remove(old_heel)

            heel_eb = edit_bones.new(heel_name)
            heel_eb.head = foot_head + Vector((0, HEEL_OFFSET_Y, HEEL_OFFSET_Z))
            heel_eb.tail = heel_eb.head + Vector((0, 0, 0.005))
            heel_eb.use_deform = False
            heel_eb.parent = foot_eb
            created += 1

            # --- Bank 가이드 ---
            bank_name = f"{foot_name}{GUIDE_SUFFIX_BANK}"
            old_bank = edit_bones.get(bank_name)
            if old_bank:
                edit_bones.remove(old_bank)

            bank_x = BANK_OFFSET_X if side == 'l' else -BANK_OFFSET_X
            bank_eb = edit_bones.new(bank_name)
            bank_eb.head = foot_head + Vector((bank_x, 0, HEEL_OFFSET_Z))
            bank_eb.tail = bank_eb.head + Vector((0, 0, 0.005))
            bank_eb.use_deform = False
            bank_eb.parent = foot_eb
            created += 1

        bpy.ops.object.mode_set(mode='OBJECT')

        # 가이드 본에 역할 프로퍼티 설정 (Pose Mode)
        bpy.ops.object.mode_set(mode='POSE')
        guide_color = (0.9, 0.9, 0.0)  # 가이드는 밝은 노랑

        for foot_name in foot_bone_names:
            for suffix, guide_role in [
                (GUIDE_SUFFIX_HEEL, f'{prefix_short}_heel_{side}'),
                (GUIDE_SUFFIX_BANK, f'{prefix_short}_bank_{side}'),
            ]:
                guide_name = f"{foot_name}{suffix}"
                pbone = preview_obj.pose.bones.get(guide_name)
                if pbone:
                    pbone[ROLE_PROP_KEY] = guide_role
                    pbone.color.palette = 'CUSTOM'
                    pbone.color.custom.normal = guide_color
                    pbone.color.custom.select = (1.0, 1.0, 0.3)
                    pbone.color.custom.active = (1.0, 1.0, 0.5)

        bpy.ops.object.mode_set(mode='OBJECT')

        # 원래 모드로 복귀
        if prev_mode == 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        return created


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 3 — ARP 리그 생성
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_BuildRig(Operator):
    """Preview Armature 기반으로 ARP 리그 생성"""
    bl_idname = "arp_convert.build_rig"
    bl_label = "ARP 리그 생성"
    bl_description = "Preview → append_arp → ref 본 위치 복사 → match_to_rig"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                preview_to_analysis, build_preview_to_ref_mapping,
                ROLE_PROP_KEY,
            )
            from arp_utils import (
                log, ensure_object_mode, select_only,
                run_arp_operator, find_arp_armature,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"모듈 임포트 실패: {e}")
            return {'CANCELLED'}

        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)

        if preview_obj is None:
            self.report({'ERROR'}, "Preview Armature가 없습니다. 먼저 [리그 분석]을 실행하세요.")
            return {'CANCELLED'}

        ensure_object_mode()

        # Step 1: ARP 리그 추가 (먼저 추가해야 실제 ref 본 이름을 알 수 있음)
        log("ARP 리그 추가 (dog 프리셋)")

        source_obj = bpy.data.objects.get(props.source_armature)
        if source_obj is None:
            self.report({'ERROR'}, f"소스 아마추어 '{props.source_armature}'를 찾을 수 없습니다.")
            return {'CANCELLED'}

        select_only(source_obj)
        try:
            run_arp_operator(bpy.ops.arp.append_arp, rig_preset='dog')
        except Exception as e:
            self.report({'ERROR'}, f"ARP 리그 추가 실패: {e}")
            return {'CANCELLED'}

        arp_obj = find_arp_armature()
        if arp_obj is None:
            self.report({'ERROR'}, "ARP 아마추어를 찾을 수 없습니다.")
            return {'CANCELLED'}

        # Step 2: Preview 본 위치 추출 (Edit 모드 1회)
        log("Preview 본 위치 추출")
        from mathutils import Vector
        from skeleton_analyzer import (
            read_preview_roles, match_chain_lengths,
        )

        ensure_object_mode()

        bpy.ops.object.select_all(action='DESELECT')
        preview_obj.select_set(True)
        bpy.context.view_layer.objects.active = preview_obj
        bpy.ops.object.mode_set(mode='EDIT')
        preview_matrix = preview_obj.matrix_world
        preview_positions = {}
        for ebone in preview_obj.data.edit_bones:
            world_head = preview_matrix @ ebone.head.copy()
            world_tail = preview_matrix @ ebone.tail.copy()
            preview_positions[ebone.name] = (world_head, world_tail, ebone.roll)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Preview 역할 읽기 (Pose 모드 데이터, Edit 불필요)
        roles = read_preview_roles(preview_obj)

        # Step 3: ARP Edit 모드 1회 진입 → ref 검색 + 매핑 + 위치 설정
        log("ARP ref 본 검색 + 위치 정렬 (단일 Edit 세션)")
        ensure_object_mode()

        bpy.ops.object.select_all(action='DESELECT')
        arp_obj.select_set(True)
        bpy.context.view_layer.objects.active = arp_obj
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = arp_obj.data.edit_bones
        arp_matrix_inv = arp_obj.matrix_world.inverted()

        # --- ref 본 인라인 검색 (Edit 모드 안에서) ---
        ref_names = set()
        ref_depth = {}
        for eb in edit_bones:
            if '_ref' in eb.name:
                ref_names.add(eb.name)
                d = 0
                p = eb.parent
                while p:
                    d += 1
                    p = p.parent
                ref_depth[eb.name] = d

        log(f"  ARP ref 본 발견: {len(ref_names)}개")

        # 역할별 ref 본 분류 (인라인)
        LEG_PREFIXES = ['thigh', 'leg']
        FOOT_PREFIXES = ['foot', 'toes']
        FOOT_AUX_PREFIXES = ['foot_bank', 'foot_heel']

        arp_chains = {}

        # Root/Spine/Neck/Head/Tail
        for name in ref_names:
            if name.startswith('root_ref'):
                arp_chains.setdefault('root', []).append(name)
            elif 'spine_' in name and '_ref' in name:
                arp_chains.setdefault('spine', []).append(name)
            elif 'neck' in name and '_ref' in name:
                arp_chains.setdefault('neck', []).append(name)
            elif name.startswith('head_ref'):
                arp_chains.setdefault('head', []).append(name)
            elif 'tail_' in name and '_ref' in name:
                arp_chains.setdefault('tail', []).append(name)

        # 정렬
        for key in ['root', 'spine', 'neck', 'head', 'tail']:
            if key in arp_chains:
                arp_chains[key] = sorted(arp_chains[key],
                    key=lambda x: ref_depth.get(x, 0))

        # Legs/Feet/Ear (side별)
        for side_suffix, side_key in [('.l', 'l'), ('.r', 'r')]:
            for is_dupli, leg_prefix in [(False, 'back'), (True, 'front')]:
                # Leg
                leg_bones = []
                for pfx in LEG_PREFIXES:
                    cands = [n for n in ref_names
                             if n.startswith(pfx) and '_ref' in n
                             and n.endswith(side_suffix)
                             and ('dupli' in n) == is_dupli
                             and 'bank' not in n and 'heel' not in n]
                    if cands:
                        cands.sort(key=lambda x: ref_depth.get(x, 0))
                        leg_bones.append(cands[0])
                if leg_bones:
                    leg_bones.sort(key=lambda x: ref_depth.get(x, 0))
                    arp_chains[f'{leg_prefix}_leg_{side_key}'] = leg_bones

                # Foot
                foot_bones = []
                for pfx in FOOT_PREFIXES:
                    cands = [n for n in ref_names
                             if n.startswith(pfx) and '_ref' in n
                             and n.endswith(side_suffix)
                             and ('dupli' in n) == is_dupli
                             and 'bank' not in n and 'heel' not in n]
                    if cands:
                        cands.sort(key=lambda x: ref_depth.get(x, 0))
                        foot_bones.append(cands[0])
                if foot_bones:
                    foot_bones.sort(key=lambda x: ref_depth.get(x, 0))
                    arp_chains[f'{leg_prefix}_foot_{side_key}'] = foot_bones

                # Bank/Heel
                for aux_pfx in FOOT_AUX_PREFIXES:
                    aux_key = aux_pfx.replace('foot_', '')
                    cands = [n for n in ref_names
                             if n.startswith(aux_pfx) and '_ref' in n
                             and n.endswith(side_suffix)
                             and ('dupli' in n) == is_dupli]
                    if cands:
                        arp_chains[f'{leg_prefix}_{aux_key}_{side_key}'] = cands

            # Ear
            ear_cands = sorted([n for n in ref_names
                                if 'ear' in n and '_ref' in n
                                and n.endswith(side_suffix)],
                               key=lambda x: ref_depth.get(x, 0))
            if ear_cands:
                arp_chains[f'ear_{side_key}'] = ear_cands

        # 검색 결과 로그
        log("  --- ARP ref 체인 ---")
        for role, bones in arp_chains.items():
            log(f"  {role:20s}: {' → '.join(bones)}")

        # --- 매핑 생성 ---
        deform_to_ref = {}
        for role, preview_bones in roles.items():
            if role in ('face', 'unmapped'):
                continue
            target_refs = arp_chains.get(role, [])
            if not target_refs:
                if 'heel' not in role and 'bank' not in role:
                    log(f"  [WARN] 역할 '{role}' → ARP ref 없음")
                continue
            chain_map = match_chain_lengths(preview_bones, target_refs)
            deform_to_ref.update(chain_map)

        log(f"  매핑 결과: {len(deform_to_ref)}개")
        for src, ref in deform_to_ref.items():
            log(f"  {src:25s} → {ref}")

        if not deform_to_ref:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'ERROR'}, "매핑 생성 실패")
            return {'CANCELLED'}

        # --- 위치 설정 (같은 Edit 세션에서) ---
        resolved = {}
        for src_name, ref_name in deform_to_ref.items():
            if src_name in preview_positions:
                resolved[ref_name] = preview_positions[src_name]

        def get_depth(bone_name):
            eb = edit_bones.get(bone_name)
            depth = 0
            while eb and eb.parent:
                depth += 1
                eb = eb.parent
            return depth

        sorted_refs = sorted(resolved.keys(), key=get_depth)
        aligned = 0

        # Phase 1: 매핑 대상만 임시 disconnect
        saved_connects = {}
        for ref_name in sorted_refs:
            ebone = edit_bones.get(ref_name)
            if ebone:
                saved_connects[ref_name] = ebone.use_connect
                ebone.use_connect = False

        # Phase 2: 위치 설정
        for ref_name in sorted_refs:
            world_head, world_tail, roll = resolved[ref_name]
            ebone = edit_bones.get(ref_name)
            if ebone is None:
                log(f"  '{ref_name}' 미발견 (skip)", "WARN")
                continue

            local_head = arp_matrix_inv @ world_head
            local_tail = arp_matrix_inv @ world_tail
            if (local_tail - local_head).length < 0.0001:
                local_tail = local_head + Vector((0, 0.01, 0))

            ebone.head = local_head
            ebone.tail = local_tail
            ebone.roll = roll
            aligned += 1

        # Phase 3: 매핑된 본끼리 gap 제거 + reconnect
        # 부모도 매핑된 본이면 parent.tail → child.head로 맞춤
        # was_connected 여부와 관계없이 항상 gap 제거
        mapped_set = set(sorted_refs)
        for ref_name in sorted_refs:
            ebone = edit_bones.get(ref_name)
            if not (ebone and ebone.parent):
                continue

            parent_name = ebone.parent.name
            if parent_name in mapped_set:
                # 부모.tail을 이 본.head로 맞춤 (gap 제거)
                ebone.parent.tail = ebone.head.copy()
                # 원래 connected였으면 복원
                if saved_connects.get(ref_name, False):
                    ebone.use_connect = True
                log(f"  체인 연결: {parent_name}.tail → {ref_name}.head")

        bpy.ops.object.mode_set(mode='OBJECT')
        log(f"ref 본 정렬 완료: {aligned}/{len(resolved)}개")

        # Step 4: match_to_rig
        log("match_to_rig 실행")

        # 진단: match_to_rig 전 주요 ref 본 존재 확인
        ensure_object_mode()
        select_only(arp_obj)
        bpy.ops.object.mode_set(mode='EDIT')
        diag_bones = arp_obj.data.edit_bones
        for check_name in ['foot_ref.l', 'foot_ref.r',
                           'foot_b_ref.l', 'foot_b_ref.r',
                           'foot_ref_dupli_001.l', 'foot_ref_dupli_001.r',
                           'foot_b_ref_dupli_001.l', 'foot_b_ref_dupli_001.r']:
            eb = diag_bones.get(check_name)
            if eb:
                log(f"  [DIAG] {check_name}: head={eb.head[:]} connected={eb.use_connect}")
        bpy.ops.object.mode_set(mode='OBJECT')

        ensure_object_mode()
        select_only(arp_obj)
        try:
            run_arp_operator(bpy.ops.arp.match_to_rig)
        except Exception as e:
            self.report({'ERROR'}, f"match_to_rig 실패: {e}")
            log(f"  match_to_rig 에러: {e}", "ERROR")
            return {'CANCELLED'}

        # Step 4: 얼굴 cc_ 커스텀 본 추가
        from skeleton_analyzer import read_preview_roles
        roles = read_preview_roles(preview_obj)
        face_bones = roles.get('face', [])
        if face_bones:
            log(f"얼굴 cc_ 커스텀 본 추가: {len(face_bones)}개")
            ensure_object_mode()
            select_only(arp_obj)
            for bone_name in face_bones:
                if bone_name not in preview_positions:
                    continue
                try:
                    run_arp_operator(bpy.ops.arp.add_custom_bone)
                except Exception as e:
                    log(f"  cc_ 추가 실패 ({bone_name}): {e}", "WARN")

        self.report({'INFO'}, f"ARP 리그 생성 완료 ({aligned}개 ref 본 정렬)")
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 4 — 리타게팅
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_Retarget(Operator):
    """동적 .bmap 생성 + 애니메이션 리타게팅"""
    bl_idname = "arp_convert.retarget"
    bl_label = "애니메이션 리타게팅"
    bl_description = "Preview 매핑으로 .bmap 자동 생성 후 리타게팅"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                preview_to_analysis, generate_bmap_content,
            )
            from arp_utils import (
                log, ensure_object_mode, select_only,
                run_arp_operator, find_arp_armature,
                ensure_retarget_context,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"모듈 임포트 실패: {e}")
            return {'CANCELLED'}

        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        source_obj = bpy.data.objects.get(props.source_armature)
        arp_obj = find_arp_armature()

        if not all([preview_obj, source_obj, arp_obj]):
            self.report({'ERROR'}, "소스/Preview/ARP 아마추어를 모두 찾을 수 없습니다.")
            return {'CANCELLED'}

        ensure_object_mode()

        # 동적 .bmap 생성
        log("동적 .bmap 생성")
        analysis = preview_to_analysis(preview_obj)
        bmap_content = generate_bmap_content(analysis)

        bmap_name = "auto_generated"
        blender_ver = f"{bpy.app.version[0]}.{bpy.app.version[1]}"

        for presets_dir in [
            os.path.join(os.environ.get("APPDATA", ""),
                "Blender Foundation", "Blender", blender_ver,
                "extensions", "user_default", "auto_rig_pro", "remap_presets"),
            os.path.join(os.environ.get("APPDATA", ""),
                "Blender Foundation", "Blender", blender_ver,
                "config", "addons", "auto_rig_pro-master", "remap_presets"),
        ]:
            if os.path.isdir(presets_dir):
                bmap_path = os.path.join(presets_dir, f"{bmap_name}.bmap")
                with open(bmap_path, 'w', encoding='utf-8') as f:
                    f.write(bmap_content)
                log(f".bmap 저장: {bmap_path}")
                break

        # 리타게팅 설정
        log("리타게팅 설정")
        try:
            ensure_retarget_context(source_obj, arp_obj)
            run_arp_operator(bpy.ops.arp.auto_scale)
            ensure_object_mode()
            run_arp_operator(bpy.ops.arp.build_bones_list)

            try:
                run_arp_operator(bpy.ops.arp.import_config_preset, preset_name=bmap_name)
                log(f".bmap 로드 성공: {bmap_name}")
            except Exception as e:
                log(f".bmap 로드 실패: {e}", "WARN")

            run_arp_operator(bpy.ops.arp.redefine_rest_pose, preserve=True)
            run_arp_operator(bpy.ops.arp.save_pose_rest)
            ensure_object_mode()
        except Exception as e:
            self.report({'ERROR'}, f"리타게팅 설정 실패: {e}")
            log(traceback.format_exc(), "ERROR")
            return {'CANCELLED'}

        # 액션별 리타게팅
        log("액션별 리타게팅")
        actions = list(bpy.data.actions)
        success = 0
        fail = 0

        for i, action in enumerate(actions):
            f_start = int(action.frame_range[0])
            f_end = int(action.frame_range[1])
            log(f"  [{i+1}/{len(actions)}] '{action.name}' ({f_start}~{f_end})")

            try:
                if source_obj.animation_data is None:
                    source_obj.animation_data_create()
                source_obj.animation_data.action = action

                ensure_object_mode()
                select_only(arp_obj)
                run_arp_operator(
                    bpy.ops.arp.retarget,
                    frame_start=f_start,
                    frame_end=f_end,
                    fake_user_action=True,
                    interpolation_type='LINEAR',
                )
                success += 1
            except Exception as e:
                fail += 1
                log(f"    실패: {e}", "WARN")

        self.report({'INFO'}, f"리타게팅 완료: {success}/{len(actions)} 성공")
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
# UI 패널
# ═══════════════════════════════════════════════════════════════

class ARPCONV_PT_MainPanel(Panel):
    """ARP 리그 변환 메인 패널"""
    bl_label = "ARP 리그 변환"
    bl_idname = "ARPCONV_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ARP Convert"

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props

        # Step 1: 분석 + Preview
        box = layout.box()
        box.label(text="Step 1: 분석", icon='VIEWZOOM')
        if props.source_armature:
            box.label(text=f"소스: {props.source_armature}")
        row = box.row()
        row.scale_y = 1.5
        row.operator("arp_convert.create_preview", icon='ARMATURE_DATA')

        if not props.is_analyzed:
            layout.separator()
            layout.label(text="소스 아마추어를 선택하고 분석을 실행하세요.", icon='INFO')
            return

        # 신뢰도
        layout.label(text=f"신뢰도: {props.confidence:.0%}", icon='CHECKMARK')
        if props.preview_armature:
            layout.label(text=f"Preview: {props.preview_armature}")

        layout.separator()

        # Step 2: 역할 수정
        box = layout.box()
        box.label(text="Step 2: 역할 수정", icon='BONE_DATA')
        box.label(text="본 선택 후 역할을 변경하세요:")

        # 역할 버튼 — 카테고리별 정리
        # Body
        sub = box.column(align=True)
        sub.label(text="Body:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ['root', 'spine', 'neck', 'head', 'tail']:
            op = grid.operator("arp_convert.set_role", text=role_id.capitalize())
            op.role = role_id

        # Legs
        sub = box.column(align=True)
        sub.label(text="Legs:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ['back_leg_l', 'back_leg_r', 'front_leg_l', 'front_leg_r']:
            label = role_id.replace('_', ' ').title().replace('Back Leg', 'BLeg').replace('Front Leg', 'FLeg')
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Feet (★)
        sub = box.column(align=True)
        sub.label(text="Feet (★ bank/heel 자동 생성):")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ['back_foot_l', 'back_foot_r', 'front_foot_l', 'front_foot_r']:
            label = role_id.replace('_', ' ').title().replace('Back Foot', 'BFoot').replace('Front Foot', 'FFoot')
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Head features
        sub = box.column(align=True)
        sub.label(text="Head:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ['ear_l', 'ear_r', 'face']:
            label = {'ear_l': 'Ear L', 'ear_r': 'Ear R', 'face': 'Face(cc_)'}[role_id]
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Unmapped
        row = box.row()
        op = row.operator("arp_convert.set_role", text="Unmapped")
        op.role = 'unmapped'

        # 현재 선택된 본의 역할 표시
        if context.active_object and context.active_object.type == 'ARMATURE':
            active_bone = context.active_bone
            if active_bone:
                pbone = context.active_object.pose.bones.get(active_bone.name)
                if pbone:
                    _ensure_scripts_path()
                    from skeleton_analyzer import ROLE_PROP_KEY
                    current_role = pbone.get(ROLE_PROP_KEY, 'unmapped')
                    box.separator()
                    box.label(text=f"선택: {active_bone.name}", icon='BONE_DATA')
                    box.label(text=f"현재 역할: {current_role}")

        layout.separator()

        # Step 3: 리그 생성
        box = layout.box()
        box.label(text="Step 3: 적용", icon='PLAY')
        col = box.column(align=True)
        col.scale_y = 1.3
        col.operator("arp_convert.build_rig", icon='MOD_ARMATURE')
        col.operator("arp_convert.retarget", icon='ACTION')


# ═══════════════════════════════════════════════════════════════
# 등록
# ═══════════════════════════════════════════════════════════════

classes = [
    ARPCONV_Props,
    ARPCONV_OT_CreatePreview,
    ARPCONV_OT_SetRole,
    ARPCONV_OT_BuildRig,
    ARPCONV_OT_Retarget,
    ARPCONV_PT_MainPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.arp_convert_props = PointerProperty(type=ARPCONV_Props)


def unregister():
    del bpy.types.Scene.arp_convert_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
