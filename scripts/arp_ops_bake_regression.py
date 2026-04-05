"""
arp_convert_addon에서 분리한 Bake / Regression 오퍼레이터.

Step 4 (Bake Animation)와 Regression 테스트 실행을 담당한다.
"""

import json
import os
import time
import traceback

import bpy
from bpy.types import Operator

from arp_fixture_io import (
    _apply_fixture_roles,
    _default_regression_report_dir,
    _load_regression_fixture,
    _resolve_regression_path,
)


class ARPCONV_OT_BakeAnimation(Operator):
    """COPY_TRANSFORMS 기반 애니메이션 베이크"""

    bl_idname = "arp_convert.bake_animation"
    bl_label = "애니메이션 베이크"
    bl_description = "소스 애니메이션을 ARP FK 컨트롤러에 COPY_TRANSFORMS로 베이크"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from arp_utils import (
            BAKE_PAIRS_KEY,
            bake_all_actions,
            deserialize_bone_pairs,
            find_arp_armature,
            find_source_armature,
            log,
            preflight_check_transforms,
        )

        source_obj = find_source_armature()
        if source_obj is None:
            self.report({"ERROR"}, "소스 아마추어를 찾을 수 없습니다.")
            return {"CANCELLED"}

        arp_obj = find_arp_armature()
        if arp_obj is None:
            self.report({"ERROR"}, "ARP 아마추어를 찾을 수 없습니다.")
            return {"CANCELLED"}

        raw_pairs = arp_obj.get(BAKE_PAIRS_KEY)
        if not raw_pairs:
            self.report({"ERROR"}, "bone_pairs가 없습니다. Build Rig를 먼저 실행하세요.")
            return {"CANCELLED"}

        bone_pairs = deserialize_bone_pairs(raw_pairs)
        if not bone_pairs:
            self.report({"ERROR"}, "bone_pairs가 비어있습니다.")
            return {"CANCELLED"}

        error = preflight_check_transforms(source_obj, arp_obj)
        if error:
            self.report({"ERROR"}, f"Preflight 실패: {error}")
            return {"CANCELLED"}

        log("=" * 50)
        log("Step 4: 애니메이션 베이크 (COPY_TRANSFORMS)")
        log("=" * 50)

        created = bake_all_actions(source_obj, arp_obj, bone_pairs)

        self.report({"INFO"}, f"베이크 완료: {len(created)}개 액션 생성")
        return {"FINISHED"}


class ARPCONV_OT_RunRegression(Operator):
    """Fixture 기반 Preview 회귀 테스트"""

    bl_idname = "arp_convert.run_regression"
    bl_label = "회귀 테스트 실행"
    bl_description = "Fixture JSON으로 역할을 적용하고 BuildRig까지 자동 실행"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from arp_convert_addon import _ensure_scripts_path, _reload_modules

        _ensure_scripts_path()
        _reload_modules()

        try:
            from arp_utils import log
        except ImportError as e:
            self.report({"ERROR"}, f"모듈 임포트 실패: {e}")
            return {"CANCELLED"}

        props = context.scene.arp_convert_props
        fixture_path = props.regression_fixture.strip()
        if not fixture_path:
            self.report({"ERROR"}, "Fixture JSON 경로를 지정하세요.")
            return {"CANCELLED"}

        started = time.time()
        report = {
            "success": False,
            "fixture_path": "",
            "report_path": "",
            "source_armature": "",
            "preview_armature": "",
            "build_rig": False,
            "role_application": {},
            "warnings": [],
            "elapsed_sec": 0.0,
        }

        try:
            fixture_data = _load_regression_fixture(fixture_path)
            report["fixture_path"] = fixture_data["path"]
            log(f"회귀 테스트 fixture 로드: {fixture_data['path']}")

            result = bpy.ops.arp_convert.create_preview()
            if "FINISHED" not in result:
                raise RuntimeError("Preview 생성 실패")

            preview_obj = bpy.data.objects.get(props.preview_armature)
            source_obj = bpy.data.objects.get(props.source_armature)
            if preview_obj is None or source_obj is None:
                raise RuntimeError("Preview 또는 source armature를 찾을 수 없습니다.")

            report["preview_armature"] = preview_obj.name
            report["source_armature"] = source_obj.name

            role_summary = _apply_fixture_roles(context, preview_obj, fixture_data)
            report["role_application"] = role_summary
            if role_summary["missing_bones"]:
                report["warnings"].append(
                    f"fixture bone 미발견: {', '.join(role_summary['missing_bones'])}"
                )
            if role_summary["duplicate_bones"]:
                report["warnings"].append(
                    f"중복 role 지정 본 {len(role_summary['duplicate_bones'])}개"
                )

            log(
                "회귀 테스트 역할 적용: "
                f"{role_summary['assigned_count']}개 본, "
                f"가이드 {role_summary['guide_count']}개"
            )

            result = bpy.ops.arp_convert.build_rig()
            if "FINISHED" not in result:
                raise RuntimeError("BuildRig 실패")
            report["build_rig"] = True

            report["success"] = True
            self.report({"INFO"}, "회귀 테스트 완료")
            return {"FINISHED"}

        except Exception as e:
            log(f"회귀 테스트 실패: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            self.report({"ERROR"}, f"회귀 테스트 실패: {e}")
            report["warnings"].append(str(e))
            return {"CANCELLED"}

        finally:
            report["elapsed_sec"] = round(time.time() - started, 2)
            report_dir = _resolve_regression_path(props.regression_report_dir.strip())
            if not report_dir:
                report_dir = _default_regression_report_dir()
            os.makedirs(report_dir, exist_ok=True)

            blend_name = os.path.splitext(os.path.basename(bpy.data.filepath or "untitled.blend"))[
                0
            ]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f"{blend_name}_{timestamp}.json")
            report["report_path"] = report_path
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            try:
                from arp_utils import log

                log(f"회귀 테스트 리포트 저장: {report_path}")
            except Exception:
                pass
