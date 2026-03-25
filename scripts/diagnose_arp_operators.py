"""
ARP 오퍼레이터 진단 스크립트
==============================
Blender에서 실행: 텍스트 에디터에 붙여넣고 ▶ 버튼 클릭

ARP 주요 오퍼레이터의 파라미터, 설명, 호출 요구사항을 출력합니다.
결과를 복사해서 공유해주세요.
"""

import inspect
import os

import bpy

# ─── 조사 대상 오퍼레이터 ───
TARGET_OPERATORS = [
    # 리그 생성 관련
    ("arp", "append_arp"),
    ("arp", "add_limb"),
    ("arp", "import_rig_data"),
    ("arp", "export_rig_data"),
    ("arp", "import_rig_data_options"),
    ("arp", "export_rig_data_options"),
    ("arp", "match_to_rig"),
    ("arp", "edit_ref"),
    ("arp", "auto_scale"),
    ("arp", "align_wings"),
    # 바인딩 관련
    ("arp", "bind_to_rig"),
    ("arp", "unbind_to_rig"),
    # 리타게팅/리맵 관련
    ("arp", "retarget"),
    ("arp", "retarget_bind_only"),
    ("arp", "batch_retarget"),
    ("arp", "build_bones_list"),
    ("arp", "import_config_preset"),
    ("arp", "remap_update"),
    ("arp", "remap_enable_all_actions"),
    ("arp", "remap_disable_all_actions"),
    ("arp", "remap_export_preset"),
    ("arp", "remap_import_act_list"),
    ("arp", "remap_export_act_list"),
    ("arp", "toggle_action_remap"),
    # 포즈 관련
    ("arp", "redefine_rest_pose"),
    ("arp", "save_pose_rest"),
    ("arp", "reset_pose"),
    ("arp", "apply_pose_as_rest"),
    # 익스포트 관련
    ("arp", "export"),
    ("arp", "check_rig_export"),
    ("arp", "fix_rig_export"),
    ("arp_export_scene", "fbx"),
    # 기타
    ("arp", "set_character_name"),
    ("arp", "save_armature_preset"),
    ("arp", "update_armature"),
    ("arp", "delete_arp"),
]


def get_operator_info(module_name, op_name):
    """오퍼레이터의 상세 정보를 추출"""
    try:
        module = getattr(bpy.ops, module_name)
        op = getattr(module, op_name)
    except AttributeError:
        return None

    info = {
        "name": f"bpy.ops.{module_name}.{op_name}",
        "exists": True,
        "properties": [],
        "description": "",
        "poll_info": "",
    }

    # rna 정보에서 프로퍼티 추출
    try:
        # get_rna_type()으로 프로퍼티 정보 획득
        rna = op.get_rna_type()
        info["description"] = rna.description or "(설명 없음)"

        for prop in rna.properties:
            if prop.identifier == "rna_type":
                continue
            prop_info = {
                "name": prop.identifier,
                "type": prop.type,
                "description": prop.description or "",
            }
            # 기본값 추출
            if hasattr(prop, "default"):
                prop_info["default"] = str(prop.default)
            # enum인 경우 선택지 추출
            if prop.type == "ENUM" and hasattr(prop, "enum_items"):
                items = [(item.identifier, item.name) for item in prop.enum_items]
                prop_info["enum_items"] = items
            # 숫자 범위
            if prop.type in ("INT", "FLOAT") and hasattr(prop, "hard_min"):
                prop_info["range"] = f"[{prop.hard_min}, {prop.hard_max}]"

            info["properties"].append(prop_info)
    except Exception as e:
        info["rna_error"] = str(e)

    return info


def main():
    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append("ARP 오퍼레이터 진단 결과")
    output_lines.append(f"Blender 버전: {bpy.app.version_string}")
    output_lines.append(
        f"ARP 모듈 존재: arp={hasattr(bpy.ops, 'arp')}, arp_export_scene={hasattr(bpy.ops, 'arp_export_scene')}"
    )
    output_lines.append("=" * 70)

    found_count = 0
    missing_count = 0

    for module_name, op_name in TARGET_OPERATORS:
        output_lines.append("")
        info = get_operator_info(module_name, op_name)

        if info is None:
            output_lines.append(f"❌ bpy.ops.{module_name}.{op_name} — 존재하지 않음")
            missing_count += 1
            continue

        found_count += 1
        output_lines.append(f"✅ {info['name']}")
        output_lines.append(f"   설명: {info['description']}")

        if "rna_error" in info:
            output_lines.append(f"   ⚠️ RNA 정보 추출 실패: {info['rna_error']}")
        elif info["properties"]:
            output_lines.append(f"   파라미터 ({len(info['properties'])}개):")
            for prop in info["properties"]:
                line = f"     - {prop['name']} ({prop['type']})"
                if prop.get("description"):
                    line += f": {prop['description']}"
                if prop.get("default"):
                    line += f" [기본값: {prop['default']}]"
                if prop.get("range"):
                    line += f" 범위: {prop['range']}"
                output_lines.append(line)

                if prop.get("enum_items"):
                    for item_id, item_name in prop["enum_items"]:
                        output_lines.append(f"       • {item_id} = {item_name}")
        else:
            output_lines.append("   파라미터: 없음")

    output_lines.append("")
    output_lines.append("=" * 70)
    output_lines.append(f"요약: {found_count}개 발견, {missing_count}개 누락")
    output_lines.append("=" * 70)

    # 결과 출력
    result_text = "\n".join(output_lines)
    print(result_text)

    # 파일로도 저장 (프로젝트 루트)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_path = os.path.join(project_root, "arp_diagnosis_result.txt")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"\n📄 결과가 파일로도 저장됨: {output_path}")
    except Exception as e:
        print(f"\n⚠️ 파일 저장 실패: {e}")
        print("위 출력을 직접 복사해주세요.")


if __name__ == "__main__":
    main()
