"""
skeleton_analyzer 분석 로직 테스트
==================================
Blender 없이 JSON fixture로 구조 분석 결과를 검증.

fixture 생성:
  Blender에서 scripts/extract_test_fixture.py 실행 → tests/fixtures/<name>.json

실행:
  pytest tests/test_skeleton_analyzer.py -v
"""

import json
import os

import pytest

import skeleton_analyzer as sa

# ─── fixture 로드 ───

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    """JSON fixture를 로드하여 (all_bones, weighted_bones) 반환."""
    path = os.path.join(FIXTURES_DIR, f"{name}.json")
    if not os.path.exists(path):
        pytest.skip(f"fixture 없음: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # JSON 리스트를 튜플로 변환 (vec 연산 호환)
    all_bones = {}
    for bname, binfo in data["all_bones"].items():
        bone = dict(binfo)
        bone["head"] = tuple(bone["head"])
        bone["tail"] = tuple(bone["tail"])
        bone["direction"] = tuple(bone["direction"])
        all_bones[bname] = bone
    weighted_bones = set(data["weighted_bones"]) if data.get("weighted_bones") is not None else None
    return all_bones, weighted_bones


def run_analysis(all_bones, weighted_bones=None):
    """
    fixture의 all_bones로 전체 분석 파이프라인 실행.
    extract_bone_data()를 건너뛰고 순수 분석 로직만 실행.
    """
    deform_bones, _ = sa.filter_deform_bones(all_bones, weighted_bones)
    sa._reconstruct_spatial_hierarchy(deform_bones, all_bones)

    root_result = sa.find_root_bone(deform_bones)
    if not root_result:
        return None

    root_name = root_result[0]
    spine_chain = sa.trace_spine_chain(root_name, deform_bones)

    spine_body = spine_chain[1:] if len(spine_chain) > 1 else []

    head_name = None
    neck_bones = []
    spine_only = list(spine_body)

    if len(spine_body) >= 2:
        head_name = spine_body[-1]
        if len(spine_body) >= 3:
            core_bones = spine_body[:-2] if len(spine_body) > 3 else spine_body[:1]
            avg_len = (
                sum(deform_bones[n]["length"] for n in core_bones) / len(core_bones)
                if core_bones
                else 1.0
            )
            neck_start = len(spine_body) - 1
            for i in range(len(spine_body) - 2, 0, -1):
                bone = deform_bones[spine_body[i]]
                prev_bone = deform_bones[spine_body[i - 1]]
                length_ratio = bone["length"] / avg_len if avg_len > 0 else 1.0
                dot = sa.vec_dot(bone["direction"], prev_bone["direction"])
                is_neck = (length_ratio < 0.7) or (dot < 0.7 and length_ratio < 1.0)
                if is_neck:
                    neck_start = i
                else:
                    break
            spine_only = spine_body[:neck_start]
            neck_bones = spine_body[neck_start:-1]
            if not spine_only and neck_bones:
                spine_only = [neck_bones[0]]
                neck_bones = neck_bones[1:]
        else:
            spine_only = spine_body[:-1]

    branches = sa.find_downward_branches(spine_chain, deform_bones)
    legs = sa.classify_legs(branches, spine_chain, deform_bones)

    leg_foot_pairs = {}
    for key in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
        if legs.get(key):
            leg_part, foot_part = sa.split_leg_foot(legs[key], deform_bones)
            legs[key] = leg_part
            if foot_part:
                foot_key = key.replace("_leg_", "_foot_")
                leg_foot_pairs[foot_key] = foot_part

    tail_chain = sa.find_tail_chain(root_name, spine_chain, deform_bones)

    face_features = (
        sa.find_head_features(head_name, deform_bones)
        if head_name
        else {"face_bones": [], "ear_l": [], "ear_r": []}
    )

    # pole vector 탐색 (all_bones 기준 — deform 여부 무관)
    pole_vectors = sa.find_pole_vectors(all_bones, legs, leg_foot_pairs)

    return {
        "root": root_name,
        "spine": spine_only,
        "neck": neck_bones,
        "head": head_name,
        "legs": legs,
        "feet": leg_foot_pairs,
        "tail": tail_chain,
        "ears": {
            "ear_l": face_features.get("ear_l", []),
            "ear_r": face_features.get("ear_r", []),
        },
        "face_bones": face_features.get("face_bones", []),
        "pole_vectors": pole_vectors,
        "deform_bones": deform_bones,
    }


# ─── 기대값 정의 ───
# 각 동물별로 fixture 추출 후 여기에 기대값 추가

EXPECTED = {
    "deer": {
        "root": "pelvis",
        "spine_contains": ["spine01", "chest"],
        "neck_contains": ["neck01", "neck02"],
        "head": "head",
        "has_back_leg_l": True,
        "has_back_leg_r": True,
        "has_front_leg_l": True,
        "has_front_leg_r": True,
        "has_tail": True,
        "has_ear_l": True,
        "has_ear_r": True,
        "back_leg_l_contains": ["thigh_L", "leg_L"],
        "back_leg_r_contains": ["thigh_R", "leg_R"],
        "front_leg_l_min_count": 2,
        "front_leg_r_min_count": 2,
    },
    "fox": {
        "root": "pelvis",
        "spine_contains": ["spine01"],
        "head": "head",
        "has_back_leg_l": True,
        "has_back_leg_r": True,
        "has_front_leg_l": True,
        "has_front_leg_r": True,
        "has_tail": True,
        "has_ear_l": True,
        "has_ear_r": True,
    },
    "bear": {
        "root": "pelvis",
        "head": "head",
        "has_back_leg_l": True,
        "has_back_leg_r": True,
        "has_front_leg_l": True,
        "has_front_leg_r": True,
        "has_tail": True,
    },
    "cat": {
        "root": "Root",
        "spine_contains": ["Spine_01", "Spine_02", "Spine_03"],
        # neck: Neck_01이 spine 끝에 포함될 수 있으므로 Neck_01.001만 기대
        "neck_contains": ["Neck_01.001"],
        "head": "Head",
        "has_back_leg_l": True,
        "has_back_leg_r": True,
        "has_front_leg_l": True,
        "has_front_leg_r": True,
        "back_leg_l_contains": ["Thigh_B01_L", "Foot_B02_L"],
        "back_leg_r_contains": ["Thigh_B01_R", "Foot_B02_R"],
        "front_leg_l_min_count": 3,
        "front_leg_r_min_count": 3,
        "has_tail": True,
        "has_ear_l": True,
        "has_ear_r": True,
        # Cat fixture에는 Foot_Fpole_L/R, Foot_Bpole_L/R가 deform 본으로 포함
        "has_pole_back_l": True,
        "has_pole_back_r": True,
        "has_pole_front_l": True,
        "has_pole_front_r": True,
    },
}


# ─── 테스트 함수 ───


def get_available_fixtures():
    """사용 가능한 fixture 이름 목록."""
    if not os.path.exists(FIXTURES_DIR):
        return []
    return [os.path.splitext(f)[0] for f in os.listdir(FIXTURES_DIR) if f.endswith(".json")]


def pytest_generate_tests(metafunc):
    """fixture 파일이 있는 동물만 파라미터화."""
    if "animal_name" in metafunc.fixturenames:
        available = get_available_fixtures()
        # EXPECTED에 정의된 것 중 fixture가 있는 것만
        names = [n for n in EXPECTED if n in available]
        if not names:
            names = ["__no_fixtures__"]
        metafunc.parametrize("animal_name", names)


@pytest.fixture
def analysis(animal_name):
    """동물별 분석 결과를 반환하는 fixture."""
    if animal_name == "__no_fixtures__":
        pytest.skip("추출된 fixture 없음. Blender에서 extract_test_fixture.py 실행 필요.")
    all_bones, weighted_bones = load_fixture(animal_name)
    result = run_analysis(all_bones, weighted_bones)
    assert result is not None, f"{animal_name}: 분석 실패 (root를 찾을 수 없음)"
    return result


class TestRootDetection:
    """루트 본 식별 테스트."""

    def test_root_is_correct(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "root" in expected:
            assert analysis["root"] == expected["root"], (
                f"root가 {analysis['root']}이지만 {expected['root']}이어야 함"
            )

    def test_root_is_parentless(self, animal_name, analysis):
        root = analysis["root"]
        db = analysis["deform_bones"]
        # root는 deform_bones에서 parent=None이거나 가장 상위여야 함
        # (RECON 후에도 root가 parentless인지 확인)
        parent = db[root]["parent"]
        assert parent is None, f"root({root})의 parent가 {parent}이지만 None이어야 함"


class TestSpineChain:
    """스파인 체인 추적 테스트."""

    def test_spine_contains_expected(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "spine_contains" not in expected:
            pytest.skip("spine 기대값 미정의")
        for bone in expected["spine_contains"]:
            assert bone in analysis["spine"], (
                f"spine에 {bone}이 없음. 실제 spine: {analysis['spine']}"
            )

    def test_spine_not_empty(self, animal_name, analysis):
        assert len(analysis["spine"]) >= 1, "spine 체인이 비어있음"


class TestNeck:
    """넥 감지 테스트."""

    def test_neck_contains_expected(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "neck_contains" not in expected:
            pytest.skip("neck 기대값 미정의")
        for bone in expected["neck_contains"]:
            assert bone in analysis["neck"], f"neck에 {bone}이 없음. 실제 neck: {analysis['neck']}"


class TestHead:
    """헤드 감지 테스트."""

    def test_head_is_correct(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "head" in expected:
            assert analysis["head"] == expected["head"], (
                f"head가 {analysis['head']}이지만 {expected['head']}이어야 함"
            )


class TestLegs:
    """다리 감지 테스트."""

    def test_back_leg_l_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_back_leg_l"):
            assert analysis["legs"].get("back_leg_l"), "back_leg_l 미감지"

    def test_back_leg_r_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_back_leg_r"):
            assert analysis["legs"].get("back_leg_r"), "back_leg_r 미감지"

    def test_front_leg_l_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_front_leg_l"):
            assert analysis["legs"].get("front_leg_l"), "front_leg_l 미감지"

    def test_front_leg_r_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_front_leg_r"):
            assert analysis["legs"].get("front_leg_r"), "front_leg_r 미감지"

    def test_back_leg_l_contains(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "back_leg_l_contains" not in expected:
            pytest.skip("back_leg_l 본 목록 미정의")
        leg = analysis["legs"].get("back_leg_l", [])
        for bone in expected["back_leg_l_contains"]:
            assert bone in leg, f"back_leg_l에 {bone} 없음. 실제: {leg}"

    def test_back_leg_r_contains(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if "back_leg_r_contains" not in expected:
            pytest.skip("back_leg_r 본 목록 미정의")
        leg = analysis["legs"].get("back_leg_r", [])
        for bone in expected["back_leg_r_contains"]:
            assert bone in leg, f"back_leg_r에 {bone} 없음. 실제: {leg}"

    def test_front_leg_min_count(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        for side in ["l", "r"]:
            key = f"front_leg_{side}_min_count"
            if key in expected:
                leg = analysis["legs"].get(f"front_leg_{side}", [])
                assert len(leg) >= expected[key], (
                    f"front_leg_{side}: {len(leg)}본이지만 최소 {expected[key]}본 필요. 실제: {leg}"
                )

    def test_legs_symmetric(self, animal_name, analysis):
        """좌우 다리 감지가 대칭인지."""
        legs = analysis["legs"]
        for prefix in ["back_leg", "front_leg"]:
            l_exists = bool(legs.get(f"{prefix}_l"))
            r_exists = bool(legs.get(f"{prefix}_r"))
            assert l_exists == r_exists, f"{prefix} 비대칭: L={l_exists}, R={r_exists}"


class TestTail:
    """꼬리 감지 테스트."""

    def test_tail_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_tail"):
            assert analysis["tail"] is not None and len(analysis["tail"]) >= 1, "tail 미감지"


class TestEars:
    """귀 감지 테스트."""

    def test_ear_l_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_ear_l"):
            assert len(analysis["ears"]["ear_l"]) >= 1, "ear_l 미감지"

    def test_ear_r_exists(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_ear_r"):
            assert len(analysis["ears"]["ear_r"]) >= 1, "ear_r 미감지"

    def test_ears_symmetric(self, animal_name, analysis):
        """귀 좌우 대칭."""
        ear_l = analysis["ears"]["ear_l"]
        ear_r = analysis["ears"]["ear_r"]
        if ear_l or ear_r:
            assert len(ear_l) == len(ear_r), f"귀 비대칭: L={len(ear_l)}본, R={len(ear_r)}본"


class TestReconstruction:
    """하이어라키 재구성 테스트."""

    def test_parentless_count(self, animal_name, analysis):
        """재구성 후 parentless 본이 합리적인 수준인지."""
        db = analysis["deform_bones"]
        parentless = [n for n, b in db.items() if b["parent"] is None]
        total = len(db)
        ratio = len(parentless) / total if total > 0 else 0
        # parentless 비율이 20% 이하여야 함
        assert ratio <= 0.2, (
            f"parentless 비율 {ratio:.1%} ({len(parentless)}/{total}): {parentless}"
        )

    def test_no_cycles(self, animal_name, analysis):
        """deform 하이어라키에 순환이 없는지."""
        db = analysis["deform_bones"]
        for name in db:
            visited = set()
            current = name
            while current:
                assert current not in visited, f"순환 감지: {name} → ... → {current}"
                visited.add(current)
                current = db[current]["parent"]


class TestOverallQuality:
    """전체 분석 품질 테스트."""

    def test_mapped_ratio(self, animal_name, analysis):
        """매핑된 본 비율이 충분한지."""
        db = analysis["deform_bones"]
        total = len(db)

        mapped = set()
        mapped.add(analysis["root"])
        mapped.update(analysis["spine"])
        mapped.update(analysis["neck"])
        if analysis["head"]:
            mapped.add(analysis["head"])
        for leg in analysis["legs"].values():
            if leg:
                mapped.update(leg)
        for foot in analysis["feet"].values():
            if foot:
                mapped.update(foot)
        if analysis["tail"]:
            mapped.update(analysis["tail"])
        mapped.update(analysis["ears"]["ear_l"])
        mapped.update(analysis["ears"]["ear_r"])
        mapped.update(analysis["face_bones"])

        ratio = len(mapped) / total if total > 0 else 0
        # 최소 50% 매핑 (face/unmapped 제외 시 더 높아야 함)
        assert ratio >= 0.5, (
            f"매핑 비율 {ratio:.1%} ({len(mapped)}/{total}), "
            f"unmapped: {[n for n in db if n not in mapped]}"
        )

    def test_no_duplicate_mapping(self, animal_name, analysis):
        """같은 본이 여러 역할에 중복 매핑되지 않는지."""
        seen = {}
        roles = {
            "root": [analysis["root"]],
            "spine": analysis["spine"],
            "neck": analysis["neck"],
            "head": [analysis["head"]] if analysis["head"] else [],
        }
        for key, bones in analysis["legs"].items():
            if bones:
                roles[key] = bones
        for key, bones in analysis["feet"].items():
            if bones:
                roles[key] = bones
        if analysis["tail"]:
            roles["tail"] = analysis["tail"]
        roles["ear_l"] = analysis["ears"]["ear_l"]
        roles["ear_r"] = analysis["ears"]["ear_r"]

        duplicates = []
        for role, bones in roles.items():
            for bone in bones:
                if bone in seen:
                    duplicates.append(f"{bone}: {seen[bone]} & {role}")
                seen[bone] = role

        assert not duplicates, f"중복 매핑: {duplicates}"


class TestWeightFiltering:
    """웨이트 0 본 필터링 테스트."""

    def test_filter_excludes_zero_weight_bones(self):
        """weighted_bones에 없는 deform 본은 제외되어야 함."""
        all_bones = {
            "Root": {
                "name": "Root",
                "head": (0, 0, 0),
                "tail": (0, 0, 1),
                "roll": 0,
                "parent": None,
                "children": ["Spine", "Pole_L"],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": False,
            },
            "Spine": {
                "name": "Spine",
                "head": (0, 0, 1),
                "tail": (0, 0, 2),
                "roll": 0,
                "parent": "Root",
                "children": [],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": True,
            },
            "Pole_L": {
                "name": "Pole_L",
                "head": (1, 0, 0),
                "tail": (1, 0, 1),
                "roll": 0,
                "parent": "Root",
                "children": [],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": False,
            },
        }
        # Pole_L은 deform이지만 웨이트 없음
        weighted = {"Root", "Spine"}
        result, excluded = sa.filter_deform_bones(all_bones, weighted_bones=weighted)
        assert "Root" in result
        assert "Spine" in result
        assert "Pole_L" not in result, "웨이트 0 본이 제외되지 않음"
        assert any(e["name"] == "Pole_L" for e in excluded), "제외 본 목록에 Pole_L 포함"

    def test_filter_without_weight_info_keeps_all(self):
        """weighted_bones=None이면 모든 deform 본 유지."""
        all_bones = {
            "A": {
                "name": "A",
                "head": (0, 0, 0),
                "tail": (0, 0, 1),
                "roll": 0,
                "parent": None,
                "children": ["B"],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": False,
            },
            "B": {
                "name": "B",
                "head": (0, 0, 1),
                "tail": (0, 0, 2),
                "roll": 0,
                "parent": "A",
                "children": [],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": True,
            },
        }
        result, excluded = sa.filter_deform_bones(all_bones, weighted_bones=None)
        assert len(result) == 2, "weighted_bones=None이면 모든 deform 본 유지"
        assert excluded == [], "weighted_bones=None이면 제외 목록 빈 리스트"

    def test_non_deform_bones_still_excluded(self):
        """non-deform 본은 웨이트와 관계없이 제외."""
        all_bones = {
            "Deform": {
                "name": "Deform",
                "head": (0, 0, 0),
                "tail": (0, 0, 1),
                "roll": 0,
                "parent": None,
                "children": [],
                "is_deform": True,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": False,
            },
            "NonDeform": {
                "name": "NonDeform",
                "head": (0, 0, 0),
                "tail": (0, 0, 1),
                "roll": 0,
                "parent": None,
                "children": [],
                "is_deform": False,
                "direction": (0, 0, 1),
                "length": 1,
                "use_connect": False,
            },
        }
        weighted = {"Deform", "NonDeform"}
        result, excluded = sa.filter_deform_bones(all_bones, weighted_bones=weighted)
        assert "Deform" in result
        assert "NonDeform" not in result, "non-deform 본은 웨이트와 관계없이 제외"
        assert excluded == [], "non-deform 본은 제외 목록에 포함되지 않음"


class TestPoleVectors:
    """IK pole vector 감지 테스트."""

    def test_pole_detected_for_back_legs(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_pole_back_l"):
            assert "back_leg_l" in analysis["pole_vectors"], "back_leg_l pole 미감지"
        if expected.get("has_pole_back_r"):
            assert "back_leg_r" in analysis["pole_vectors"], "back_leg_r pole 미감지"

    def test_pole_detected_for_front_legs(self, animal_name, analysis):
        expected = EXPECTED[animal_name]
        if expected.get("has_pole_front_l"):
            assert "front_leg_l" in analysis["pole_vectors"], "front_leg_l pole 미감지"
        if expected.get("has_pole_front_r"):
            assert "front_leg_r" in analysis["pole_vectors"], "front_leg_r pole 미감지"

    def test_pole_names_contain_pole_keyword(self, animal_name, analysis):
        """감지된 pole 본 이름에 pole 키워드가 포함되어야 함."""
        for key, pole_info in analysis.get("pole_vectors", {}).items():
            name_lower = pole_info["name"].lower()
            assert any(kw in name_lower for kw in ["pole", "knee", "elbow"]), (
                f"{key} pole 본 이름에 키워드 없음: {pole_info['name']}"
            )


class TestShapeKeyDriverParsing:
    """Shape key 드라이버 파싱 유틸리티 테스트 (bpy 불필요)."""

    def test_extract_shape_key_name_standard(self):
        result = sa._extract_shape_key_name('key_blocks["SmileMouth"].value')
        assert result == "SmileMouth"

    def test_extract_shape_key_name_with_spaces(self):
        result = sa._extract_shape_key_name('key_blocks["Open Jaw"].value')
        assert result == "Open Jaw"

    def test_extract_shape_key_name_fallback(self):
        result = sa._extract_shape_key_name("unknown_path")
        assert result == "unknown_path"

    def test_extract_bone_from_data_path_standard(self):
        result = sa._extract_bone_from_data_path('pose.bones["CtrlJaw"]["jaw_open"]')
        assert result == "CtrlJaw"

    def test_extract_bone_from_data_path_no_match(self):
        result = sa._extract_bone_from_data_path("some.other.path")
        assert result is None

    def test_extract_bone_from_data_path_with_dots(self):
        result = sa._extract_bone_from_data_path('pose.bones["Ctrl.Jaw.001"]["value"]')
        assert result == "Ctrl.Jaw.001"


# ═══════════════════════════════════════════════════════════════
# match_chain_lengths 테스트
# ═══════════════════════════════════════════════════════════════


class TestMatchChainLengths:
    """match_chain_lengths() 체인 매칭 테스트."""

    def test_equal_lengths(self):
        result = sa.match_chain_lengths(["a", "b", "c"], ["X", "Y", "Z"])
        assert result == {"a": "X", "b": "Y", "c": "Z"}

    def test_source_longer_all_mapped(self):
        """소스가 길 때 모든 소스 본이 매핑되어야 함."""
        src = ["a", "b", "c", "d", "e"]
        tgt = ["X", "Y", "Z"]
        result = sa.match_chain_lengths(src, tgt)
        assert set(result.keys()) == set(src), "모든 소스 본이 매핑에 포함되어야 함"
        assert result["a"] == "X", "첫 소스 → 첫 타겟"
        assert result["e"] == "Z", "마지막 소스 → 마지막 타겟"

    def test_source_longer_two_to_one(self):
        """소스 2개 → 타겟 1개: 모두 같은 타겟에 매핑."""
        result = sa.match_chain_lengths(["a", "b"], ["X"])
        assert result == {"a": "X", "b": "X"}

    def test_source_shorter(self):
        """소스가 짧으면 루트부터 순서대로."""
        result = sa.match_chain_lengths(["a", "b"], ["X", "Y", "Z"])
        assert result == {"a": "X", "b": "Y"}

    def test_empty_source(self):
        assert sa.match_chain_lengths([], ["X"]) == {}

    def test_empty_target(self):
        assert sa.match_chain_lengths(["a"], []) == {}

    def test_single_to_single(self):
        assert sa.match_chain_lengths(["a"], ["X"]) == {"a": "X"}


# ═══════════════════════════════════════════════════════════════
# generate_arp_mapping 스킵 역할 보고 테스트
# ═══════════════════════════════════════════════════════════════


class TestGenerateArpMappingSkippedRoles:
    """generate_arp_mapping()이 매핑 불가 역할을 보고하는지."""

    def test_skipped_roles_returned(self):
        analysis = {
            "chains": {
                "root": {"bones": ["root_bone"]},
                "unknown_xyz_role": {"bones": ["some_bone"]},
            },
            "confidence": 0.5,
        }
        result = sa.generate_arp_mapping(analysis)
        assert "skipped_roles" in result
        assert "unknown_xyz_role" in result["skipped_roles"]
        assert "root" not in result["skipped_roles"]

    def test_no_skipped_roles_when_all_mapped(self):
        analysis = {
            "chains": {
                "root": {"bones": ["center"]},
                "spine": {"bones": ["spine01", "spine02"]},
            },
            "confidence": 0.8,
        }
        result = sa.generate_arp_mapping(analysis)
        assert result.get("skipped_roles", []) == []


class TestRoleMapConsistency:
    """ARP_REF_MAP과 _CTRL_SEARCH_PATTERNS의 역할별 일관성을 보장한다.

    단일 본 역할(non-multi)에 대해 ref 맵과 ctrl 검색 패턴이 서로
    동기화되어 있는지 Python 레벨에서 검증한다. F12 베이크에서 발생한
    back_leg shoulder 누락 같은 불일치 버그를 조기에 잡기 위한 회귀 테스트.
    """

    def test_ref_map_and_ctrl_patterns_cover_same_roles(self):
        """단일 본 역할은 ref_map과 ctrl_patterns에 모두 등장해야 한다."""
        single_roles = set(sa.ARP_REF_MAP) - sa._MULTI_BONE_ROLES
        for role in single_roles:
            assert role in sa._CTRL_SEARCH_PATTERNS, f"{role} missing in _CTRL_SEARCH_PATTERNS"

    def test_single_bone_ctrl_patterns_cover_all_refs(self):
        """단일 본 역할에서 ctrl 패턴 수는 ref 수 이상이어야 한다.

        humanoid fallback 패턴이 함께 나열되는 경우가 있으므로 >=로 검사.
        """
        for role, refs in sa.ARP_REF_MAP.items():
            if role in sa._MULTI_BONE_ROLES:
                continue
            patterns = sa._CTRL_SEARCH_PATTERNS.get(role, [])
            assert len(patterns) >= len(refs), (
                f"{role}: refs={len(refs)} > ctrl_patterns={len(patterns)}"
            )

    def test_back_leg_patterns_start_with_thigh_b(self):
        """dog 3-bone 뒷다리의 shoulder(c_thigh_b)는 첫 패턴이어야 한다."""
        assert sa._CTRL_SEARCH_PATTERNS["back_leg_l"][0] == r"^c_thigh_b\.l"
        assert sa._CTRL_SEARCH_PATTERNS["back_leg_r"][0] == r"^c_thigh_b\.r"

    def test_front_leg_patterns_start_with_thigh_b_dupli(self):
        """dog 3-bone 앞다리의 shoulder(c_thigh_b_dupli)는 첫 패턴이어야 한다."""
        assert sa._CTRL_SEARCH_PATTERNS["front_leg_l"][0] == r"^c_thigh_b_dupli_\d+\.l"
        assert sa._CTRL_SEARCH_PATTERNS["front_leg_r"][0] == r"^c_thigh_b_dupli_\d+\.r"


class TestApplyIkToFootCtrl:
    """F12 bake 시 FK foot 컨트롤러를 IK foot effector로 변환하는 헬퍼 검증.

    이 헬퍼는 back_foot/front_foot 역할의 소스 본이 IK 모드 애니메이션에서
    올바르게 c_foot_ik 계열 컨트롤러로 매핑되도록 보장한다. 정규식이 c_toes
    계열만 다뤘던 과거 구현은 back_foot 패턴이 c_foot_fk를 첫 매칭으로 돌려
    주기 시작한 뒤 fall-through 버그를 일으켰음 (2026-04-05 F12 부작용).
    """

    def test_c_toes_l_converts_to_c_foot_ik_l(self):
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_toes.l", "back_foot_l")
        assert ik == "c_foot_ik.l"
        assert pole == "c_leg_pole.l"
        assert is_ik is True

    def test_c_toes_fk_r_converts_to_c_foot_ik_r(self):
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_toes_fk.r", "back_foot_r")
        assert ik == "c_foot_ik.r"
        assert pole == "c_leg_pole.r"
        assert is_ik is True

    def test_c_toes_fk_dupli_converts_to_c_foot_ik_dupli(self):
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_toes_fk_dupli_001.l", "front_foot_l")
        assert ik == "c_foot_ik_dupli_001.l"
        assert pole == "c_leg_pole_dupli_001.l"
        assert is_ik is True

    def test_c_foot_fk_l_converts_to_c_foot_ik_l(self):
        """c_foot_fk 계열도 c_foot_ik로 변환되어야 한다 (back_foot 패턴
        수정 이후 doubled 매칭 fall-through 방지)."""
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_foot_fk.l", "back_foot_l")
        assert ik == "c_foot_ik.l"
        assert pole == "c_leg_pole.l"
        assert is_ik is True

    def test_c_foot_fk_r_converts_to_c_foot_ik_r(self):
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_foot_fk.r", "back_foot_r")
        assert ik == "c_foot_ik.r"
        assert pole == "c_leg_pole.r"
        assert is_ik is True

    def test_c_foot_fk_dupli_converts_to_c_foot_ik_dupli(self):
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_foot_fk_dupli_001.l", "front_foot_l")
        assert ik == "c_foot_ik_dupli_001.l"
        assert pole == "c_leg_pole_dupli_001.l"
        assert is_ik is True


class TestChainsToFlatRoles:
    """chains_to_flat_roles() 순수 함수 테스트."""

    def test_basic_conversion(self):
        analysis = {
            "chains": {
                "root": {"bones": ["pelvis"], "confidence": 0.95},
                "spine": {"bones": ["sp1", "sp2"], "confidence": 0.9},
            },
            "unmapped": ["eye_L", "jaw"],
        }
        result = sa.chains_to_flat_roles(analysis)
        assert result["root"] == ["pelvis"]
        assert result["spine"] == ["sp1", "sp2"]
        assert result["unmapped"] == ["eye_L", "jaw"]

    def test_no_unmapped(self):
        analysis = {
            "chains": {"root": {"bones": ["Root"], "confidence": 1.0}},
            "unmapped": [],
        }
        result = sa.chains_to_flat_roles(analysis)
        assert result == {"root": ["Root"]}
        assert "unmapped" not in result

    def test_empty_analysis(self):
        result = sa.chains_to_flat_roles({})
        assert result == {}

    def test_full_fox_roles(self):
        analysis = {
            "chains": {
                "root": {"bones": ["pelvis"], "confidence": 0.95},
                "spine": {"bones": ["spine01", "spine02", "chest"], "confidence": 0.9},
                "neck": {"bones": ["neck"], "confidence": 0.9},
                "head": {"bones": ["head"], "confidence": 0.9},
                "back_leg_l": {"bones": ["thigh_L", "leg_L", "foot_L"], "confidence": 0.85},
                "tail": {"bones": ["tail_01", "tail02", "tail03", "tail04"], "confidence": 0.9},
            },
            "unmapped": ["Food", "jaw", "eye_L"],
        }
        result = sa.chains_to_flat_roles(analysis)
        assert len(result) == 7  # 6 chains + unmapped
        assert result["back_leg_l"] == ["thigh_L", "leg_L", "foot_L"]
        assert result["tail"] == ["tail_01", "tail02", "tail03", "tail04"]
        assert result["unmapped"] == ["Food", "jaw", "eye_L"]

    def test_c_hand_fk_humanoid_front_foot(self):
        """humanoid 프리셋 대비 기존 c_hand_fk 분기 유지."""
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_hand_fk.l", "front_foot_l")
        assert ik == "c_hand_ik.l"
        assert pole == "c_arm_pole.l"
        assert is_ik is True

    def test_unknown_ctrl_returns_is_ik_false(self):
        """매칭되지 않는 컨트롤러는 (입력, '', False)를 그대로 돌려준다."""
        ik, pole, is_ik = sa._apply_ik_to_foot_ctrl("c_random_ctrl.l", "back_foot_l")
        assert ik == "c_random_ctrl.l"
        assert pole == ""
        assert is_ik is False


# ═══════════════════════════════════════════════════════════════
# Collapse / Orphan / Trajectory 회귀 테스트
# ═══════════════════════════════════════════════════════════════


def _make_bone(head, tail, parent=None, children=None, is_deform=True, name=None):
    """테스트용 본 딕셔너리 생성 헬퍼."""
    h = tuple(head)
    t = tuple(tail)
    d = tuple(t[i] - h[i] for i in range(3))
    length = sum(x * x for x in d) ** 0.5
    if length > 0:
        d = tuple(x / length for x in d)
    return {
        "name": name or "bone",
        "head": h,
        "tail": t,
        "roll": 0,
        "parent": parent,
        "children": children or [],
        "is_deform": is_deform,
        "direction": d,
        "length": length,
        "use_connect": False,
    }


class TestCollapseNonDeform:
    """non-deform 투과(collapse) 계층 재구성 회귀 테스트.

    flat 계층 리그에서 non-deform 중간 본을 건너뛰어
    deform 본 간 부모-자식을 올바르게 확립하는지 검증.
    """

    def test_collapse_connects_through_nondeform(self):
        """non-deform 중간 본을 건너뛰어 deform 부모에 연결."""
        all_bones = {
            "root_ctrl": _make_bone((0, 0, 0), (0, 0, 0.5), children=["center"], is_deform=False),
            "center": _make_bone(
                (0, 0, 0.5),
                (0, 0, 1),
                parent="root_ctrl",
                children=["pelvis", "thigh_L"],
                is_deform=False,
            ),
            "pelvis": _make_bone(
                (0, 0, 1),
                (0, 0, 1.5),
                parent="center",
                children=["spine01"],
                is_deform=True,
            ),
            "spine01": _make_bone(
                (0, 0, 1.5),
                (0, 0, 2),
                parent="pelvis",
                children=[],
                is_deform=True,
            ),
            "thigh_L": _make_bone(
                (-0.3, 0, 0.9),
                (-0.3, 0, 0.4),
                parent="center",
                children=[],
                is_deform=True,
            ),
        }
        deform_bones, _ = sa.filter_deform_bones(all_bones)
        sa._reconstruct_spatial_hierarchy(deform_bones, all_bones)

        # pelvis-spine01 관계는 원본과 동일
        assert deform_bones["spine01"]["parent"] == "pelvis"
        # thigh_L은 non-deform center를 건너뛰어 pelvis 아래로 연결되어야 함
        assert deform_bones["thigh_L"]["parent"] is not None, "thigh_L이 orphan으로 남음"

    def test_nondeform_bones_excluded_from_deform(self):
        """non-deform 본은 filter_deform_bones 결과에 절대 포함되지 않음."""
        all_bones = {
            "ctrl": _make_bone((0, 0, 0), (0, 0, 1), children=["pelvis"], is_deform=False),
            "pelvis": _make_bone(
                (0, 0, 1),
                (0, 0, 2),
                parent="ctrl",
                children=[],
                is_deform=True,
            ),
        }
        deform_bones, _ = sa.filter_deform_bones(all_bones)
        assert "ctrl" not in deform_bones, "non-deform 본이 deform_bones에 포함됨"
        assert "pelvis" in deform_bones

    def test_deer_no_orphan_legs(self):
        """deer fixture: flat 계층에서 다리 본이 orphan으로 남지 않아야 함."""
        if not os.path.exists(os.path.join(FIXTURES_DIR, "deer.json")):
            pytest.skip("deer fixture 없음")
        all_bones, weighted = load_fixture("deer")
        result = run_analysis(all_bones, weighted)
        assert result is not None

        # 4개 다리 모두 감지되어야 함
        for side in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
            assert result["legs"].get(side), f"deer {side} 미감지 — collapse 실패 가능성"

    def test_collapse_siblings_share_nondeform_parent(self):
        """같은 non-deform 부모를 공유하는 deform 형제가 연결됨."""
        all_bones = {
            "ctrl": _make_bone(
                (0, 0, 0),
                (0, 0, 1),
                children=["pelvis", "arm_L", "arm_R"],
                is_deform=False,
            ),
            "pelvis": _make_bone(
                (0, 0, 1),
                (0, 0, 2),
                parent="ctrl",
                children=["spine"],
                is_deform=True,
            ),
            "spine": _make_bone(
                (0, 0, 2),
                (0, 0, 3),
                parent="pelvis",
                children=[],
                is_deform=True,
            ),
            "arm_L": _make_bone(
                (-1, 0, 2),
                (-1, 0, 1),
                parent="ctrl",
                children=[],
                is_deform=True,
            ),
            "arm_R": _make_bone(
                (1, 0, 2),
                (1, 0, 1),
                parent="ctrl",
                children=[],
                is_deform=True,
            ),
        }
        deform_bones, _ = sa.filter_deform_bones(all_bones)
        sa._reconstruct_spatial_hierarchy(deform_bones, all_bones)

        # arm_L/R은 같은 non-deform 부모의 형제이므로 orphan이면 안 됨
        # (pelvis나 spine에 연결되거나, 서로 형제로 연결됨)
        orphans = [n for n, b in deform_bones.items() if b["parent"] is None]
        # 최소한 하나의 루트만 있어야 함 (pelvis)
        assert len(orphans) <= 1, f"orphan이 너무 많음: {orphans}"


class TestTrajectoryDetection:
    """trajectory 역할 감지 회귀 테스트.

    root 부모 본이 trajectory로 감지되어 unmapped가 아닌
    trajectory 역할에 매핑되는지 검증.
    """

    def test_trajectory_from_deform_parent(self):
        """root의 deform 부모가 trajectory로 감지됨.

        traj 본은 아마추어 최하단(바닥)에 위치해 중심에서 멀고,
        pelvis가 중심에 있어 root로 선택된다. traj는 최상위 deform 부모로
        trajectory 역할을 받아야 한다.
        """
        # traj(바닥) → pelvis(중심) → spine → chest → head
        # + pelvis → thigh_L → leg_L → foot_L
        # + pelvis → thigh_R → leg_R → foot_R
        all_bones = {
            "traj": _make_bone(
                (0, 0, -0.5),
                (0, 0, 0),
                children=["pelvis"],
                is_deform=True,
                name="traj",
            ),
            "pelvis": _make_bone(
                (0, 0, 1),
                (0, 0, 1.5),
                parent="traj",
                children=["spine", "thigh_L", "thigh_R"],
                is_deform=True,
                name="pelvis",
            ),
            "spine": _make_bone(
                (0, 0, 1.5),
                (0, 0, 2),
                parent="pelvis",
                children=["chest"],
                is_deform=True,
                name="spine",
            ),
            "chest": _make_bone(
                (0, 0, 2),
                (0, 0, 2.5),
                parent="spine",
                children=["head"],
                is_deform=True,
                name="chest",
            ),
            "head": _make_bone(
                (0, 0, 2.5),
                (0, 0, 3),
                parent="chest",
                children=[],
                is_deform=True,
                name="head",
            ),
            "thigh_L": _make_bone(
                (-0.3, 0, 1),
                (-0.3, 0, 0.5),
                parent="pelvis",
                children=["leg_L"],
                is_deform=True,
                name="thigh_L",
            ),
            "leg_L": _make_bone(
                (-0.3, 0, 0.5),
                (-0.3, 0, 0),
                parent="thigh_L",
                children=["foot_L"],
                is_deform=True,
                name="leg_L",
            ),
            "foot_L": _make_bone(
                (-0.3, 0, 0),
                (-0.3, 0.2, 0),
                parent="leg_L",
                children=[],
                is_deform=True,
                name="foot_L",
            ),
            "thigh_R": _make_bone(
                (0.3, 0, 1),
                (0.3, 0, 0.5),
                parent="pelvis",
                children=["leg_R"],
                is_deform=True,
                name="thigh_R",
            ),
            "leg_R": _make_bone(
                (0.3, 0, 0.5),
                (0.3, 0, 0),
                parent="thigh_R",
                children=["foot_R"],
                is_deform=True,
                name="foot_R",
            ),
            "foot_R": _make_bone(
                (0.3, 0, 0),
                (0.3, 0.2, 0),
                parent="leg_R",
                children=[],
                is_deform=True,
                name="foot_R",
            ),
        }

        deform_bones, _ = sa.filter_deform_bones(all_bones)
        sa._reconstruct_spatial_hierarchy(deform_bones, all_bones)
        root_result = sa.find_root_bone(deform_bones)
        assert root_result is not None

        root_name = root_result[0]
        assert root_name == "pelvis", f"root가 {root_name}이지만 pelvis여야 함"

        # trajectory 감지: pelvis의 부모 traj가 최상위 → trajectory
        root_data = deform_bones[root_name]
        parent_name = root_data.get("parent")
        assert parent_name == "traj", f"pelvis parent={parent_name}"
        # traj의 부모는 None (최상위)
        traj_data = deform_bones["traj"]
        assert traj_data["parent"] is None, "traj는 최상위여야 함"

    def test_trajectory_not_in_unmapped_for_fixtures(self):
        """fixture 분석에서 trajectory 후보가 unmapped에 들어가지 않아야 함."""
        for fixture_name in get_available_fixtures():
            if fixture_name not in EXPECTED:
                continue
            all_bones, weighted = load_fixture(fixture_name)
            result = run_analysis(all_bones, weighted)
            if result is None:
                continue

            # root의 deform 부모가 있으면 — 그 부모는 unmapped가 아닌
            # 별도 역할(trajectory)로 매핑되어야 함
            root = result["root"]
            db = result["deform_bones"]
            root_parent = db[root]["parent"]
            if root_parent and root_parent in db:
                parent_data = db[root_parent]
                if parent_data["parent"] is None:
                    # 이 부모가 매핑된 역할에 포함되어야 함
                    all_mapped = set()
                    all_mapped.add(root)
                    all_mapped.update(result["spine"])
                    all_mapped.update(result["neck"])
                    if result["head"]:
                        all_mapped.add(result["head"])
                    for leg in result["legs"].values():
                        if leg:
                            all_mapped.update(leg)
                    for foot in result["feet"].values():
                        if foot:
                            all_mapped.update(foot)
                    if result["tail"]:
                        all_mapped.update(result["tail"])
                    all_mapped.update(result["ears"]["ear_l"])
                    all_mapped.update(result["ears"]["ear_r"])
                    # root_parent가 매핑 안 되면 → trajectory 누락 가능성
                    # (이 테스트는 run_analysis에 trajectory가 없어도 경고 수준)
                    if root_parent not in all_mapped:
                        pytest.fail(
                            f"{fixture_name}: root({root})의 부모 {root_parent}가 "
                            f"어떤 역할에도 매핑되지 않음 — trajectory 누락 가능성"
                        )


class TestNonDeformNeverInAnalysis:
    """non-deform 본이 분석 결과의 어떤 역할에도 절대 포함되지 않는지 검증."""

    def test_nondeform_bones_absent_from_all_roles(self):
        """모든 fixture에서 non-deform 본이 분석 결과에 없어야 함."""
        for fixture_name in get_available_fixtures():
            if fixture_name not in EXPECTED:
                continue
            all_bones, weighted = load_fixture(fixture_name)
            nondeform_names = {n for n, b in all_bones.items() if not b["is_deform"]}
            if not nondeform_names:
                continue

            result = run_analysis(all_bones, weighted)
            if result is None:
                continue

            # 모든 역할에서 non-deform 본 이름 체크
            all_role_bones = set()
            all_role_bones.add(result["root"])
            all_role_bones.update(result["spine"])
            all_role_bones.update(result["neck"])
            if result["head"]:
                all_role_bones.add(result["head"])
            for leg in result["legs"].values():
                if leg:
                    all_role_bones.update(leg)
            for foot in result["feet"].values():
                if foot:
                    all_role_bones.update(foot)
            if result["tail"]:
                all_role_bones.update(result["tail"])
            all_role_bones.update(result["ears"]["ear_l"])
            all_role_bones.update(result["ears"]["ear_r"])
            all_role_bones.update(result["face_bones"])

            leaked = nondeform_names & all_role_bones
            assert not leaked, f"{fixture_name}: non-deform 본이 역할에 포함됨: {leaked}"

    def test_deform_bones_dict_excludes_nondeform(self):
        """deform_bones에 non-deform 본이 절대 포함되지 않음."""
        for fixture_name in get_available_fixtures():
            if fixture_name not in EXPECTED:
                continue
            all_bones, weighted = load_fixture(fixture_name)
            result = run_analysis(all_bones, weighted)
            if result is None:
                continue

            nondeform_names = {n for n, b in all_bones.items() if not b["is_deform"]}
            leaked = nondeform_names & set(result["deform_bones"].keys())
            assert not leaked, f"{fixture_name}: non-deform 본이 deform_bones에 포함됨: {leaked}"
