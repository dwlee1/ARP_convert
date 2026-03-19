"""
Rigify ↔ ARP 본 매핑 테이블
==============================
출처: https://github.com/israelandrewbrown/AutoRigPro-to-Rigify

주의사항:
- 이 매핑은 Rigify **메타리그** 본 이름 기준 (DEF- 접두사 없음)
- 실제 변형 본(DEF-*)에 적용할 때는 'DEF-' 접두사를 제거하고 매핑
- 사이드: Rigify '.L'/'.R' (대문자) → ARP '.l'/'.r' (소문자)
- 중앙: ARP는 '.x' 접미사 사용
- spine.004는 직접 매핑 없음 (보간 처리 필요)
- 얼굴 본은 매핑 없음 (ARP가 별도 처리)
"""

# ─── 휴머노이드 기본 매핑 (Rigify 메타리그 → ARP 레퍼런스) ───
HUMANOID_MAPPING = {
    # 다리 - 좌
    "thigh.L": "thigh_ref.l",
    "shin.L": "leg_ref.l",
    "foot.L": "foot_ref.l",
    "toe.L": "toes_ref.l",
    "heel.02.L": "foot_heel_ref.l",
    # 다리 - 우
    "thigh.R": "thigh_ref.r",
    "shin.R": "leg_ref.r",
    "foot.R": "foot_ref.r",
    "toe.R": "toes_ref.r",
    "heel.02.R": "foot_heel_ref.r",
    # 몸통 / 스파인
    "spine": "root_ref.x",
    "spine.001": "spine_01_ref.x",
    "spine.002": "spine_02_ref.x",
    "spine.003": "spine_03_ref.x",
    # "spine.004": 직접 매핑 없음 — spine.003.tail과 spine.005.head 사이 보간
    "spine.005": "neck_ref.x",
    "spine.006": "head_ref.x",
    # 어깨 & 팔 - 좌
    "shoulder.L": "shoulder_ref.l",
    "upper_arm.L": "arm_ref.l",
    "forearm.L": "forearm_ref.l",
    "hand.L": "hand_ref.l",
    # 손가락 - 좌
    "palm.01.L": "index1_base_ref.l",
    "f_index.01.L": "index1_ref.l",
    "f_index.02.L": "index2_ref.l",
    "f_index.03.L": "index3_ref.l",
    "thumb.01.L": "thumb1_ref.l",
    "thumb.02.L": "thumb2_ref.l",
    "thumb.03.L": "thumb3_ref.l",
    "palm.02.L": "middle1_base_ref.l",
    "f_middle.01.L": "middle1_ref.l",
    "f_middle.02.L": "middle2_ref.l",
    "f_middle.03.L": "middle3_ref.l",
    "palm.03.L": "ring1_base_ref.l",
    "f_ring.01.L": "ring1_ref.l",
    "f_ring.02.L": "ring2_ref.l",
    "f_ring.03.L": "ring3_ref.l",
    "palm.04.L": "pinky1_base_ref.l",
    "f_pinky.01.L": "pinky1_ref.l",
    "f_pinky.02.L": "pinky2_ref.l",
    "f_pinky.03.L": "pinky3_ref.l",
    # 어깨 & 팔 - 우
    "shoulder.R": "shoulder_ref.r",
    "upper_arm.R": "arm_ref.r",
    "forearm.R": "forearm_ref.r",
    "hand.R": "hand_ref.r",
    # 손가락 - 우
    "palm.01.R": "index1_base_ref.r",
    "f_index.01.R": "index1_ref.r",
    "f_index.02.R": "index2_ref.r",
    "f_index.03.R": "index3_ref.r",
    "thumb.01.R": "thumb1_ref.r",
    "thumb.02.R": "thumb2_ref.r",
    "thumb.03.R": "thumb3_ref.r",
    "palm.02.R": "middle1_base_ref.r",
    "f_middle.01.R": "middle1_ref.r",
    "f_middle.02.R": "middle2_ref.r",
    "f_middle.03.R": "middle3_ref.r",
    "palm.03.R": "ring1_base_ref.r",
    "f_ring.01.R": "ring1_ref.r",
    "f_ring.02.R": "ring2_ref.r",
    "f_ring.03.R": "ring3_ref.r",
    "palm.04.R": "pinky1_base_ref.r",
    "f_pinky.01.R": "pinky1_ref.r",
    "f_pinky.02.R": "pinky2_ref.r",
    "f_pinky.03.R": "pinky3_ref.r",
}

# 매핑 없는 Rigify 본 (무시 대상)
UNMAPPED_RIGIFY_BONES = [
    "breast.L", "breast.R",
    "pelvis.L", "pelvis.R",
]


# ─── 사족보행 동물 확장 매핑 (Phase 1 테스트 후 보완 필요) ───
# 동물 캐릭터는 휴머노이드와 다른 구조:
# - 앞다리 = arm 계열, 뒷다리 = leg 계열
# - 꼬리(tail), 귀(ear) 등 추가 본 존재
# - 손가락 대신 발가락/발톱 구조
QUADRUPED_EXTRA_MAPPING = {
    # 꼬리 (Rigify 쪽 네이밍은 실제 파일 확인 후 보정)
    # "tail": "tail_00_ref.x",
    # "tail.001": "tail_01_ref.x",
    # "tail.002": "tail_02_ref.x",
    # ... Phase 1에서 실제 본 구조 확인 후 작성
}

# ─── 조류 확장 매핑 (Phase 3에서 작성) ───
BIRD_EXTRA_MAPPING = {
    # 날개 본 → ARP arm 계열
    # "wing.L": "arm_ref.l",
    # ... Phase 3에서 작성
}


# ─── 유틸리티 함수 ───

def rigify_to_arp_name(rigify_bone_name):
    """
    Rigify 본 이름을 ARP 레퍼런스 본 이름으로 변환.
    DEF- 접두사가 있으면 자동 제거.

    Args:
        rigify_bone_name: 'DEF-spine.001' 또는 'spine.001'
    Returns:
        ARP 본 이름 또는 None (매핑 없음)
    """
    # DEF- 접두사 제거
    clean_name = rigify_bone_name
    if clean_name.startswith("DEF-"):
        clean_name = clean_name[4:]
    if clean_name.startswith("ORG-"):
        clean_name = clean_name[4:]
    if clean_name.startswith("MCH-"):
        clean_name = clean_name[4:]

    # 매핑 검색
    if clean_name in HUMANOID_MAPPING:
        return HUMANOID_MAPPING[clean_name]
    if clean_name in QUADRUPED_EXTRA_MAPPING:
        return QUADRUPED_EXTRA_MAPPING[clean_name]
    if clean_name in BIRD_EXTRA_MAPPING:
        return BIRD_EXTRA_MAPPING[clean_name]
    if clean_name in UNMAPPED_RIGIFY_BONES:
        return None  # 의도적 무시

    return None  # 매핑 없음 — 패스스루 대상 (cc_ 접두사로 추가)


def convert_side_suffix(name):
    """Rigify 사이드 접미사를 ARP 형식으로 변환: .L→.l, .R→.r"""
    if name.endswith(".L"):
        return name[:-2] + ".l"
    elif name.endswith(".R"):
        return name[:-2] + ".r"
    return name
