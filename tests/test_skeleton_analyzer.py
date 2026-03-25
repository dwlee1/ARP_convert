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
    """JSON fixture를 로드하여 all_bones dict 반환."""
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
    return all_bones


def run_analysis(all_bones):
    """
    fixture의 all_bones로 전체 분석 파이프라인 실행.
    extract_bone_data()를 건너뛰고 순수 분석 로직만 실행.
    """
    deform_bones = sa.filter_deform_bones(all_bones)
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
    all_bones = load_fixture(animal_name)
    result = run_analysis(all_bones)
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
