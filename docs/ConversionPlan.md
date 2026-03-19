# ARP 리그 변환 계획

> 최종 수정: 2026-03-19

## 목표

소스 리그 (커스텀/Rigify 등) → ARP 리그로 변환, 애니메이션 리타게팅까지 자동화.
리그 타입별 JSON 프로필로 본 매핑 관리.

## 파이프라인

```
01_create_arp_rig.py → 02_retarget_animation.py
```

### Step 1: ARP 리그 생성 (`01_create_arp_rig.py`)

1. JSON 프로필 로드 (`mapping_profiles/*.json`)
2. 소스 아마추어 식별 (deform 본 기준)
3. ARP 프리셋 추가 (`bpy.ops.arp.append_arp`)
4. 소스 deform 본 위치 → ARP ref 본 위치 정렬
5. `bpy.ops.arp.match_to_rig()` 실행

### Step 2: 애니메이션 리타게팅 (`02_retarget_animation.py`)

1. 소스/ARP 아마추어 식별
2. ARP Remap 설정 (`auto_scale` → `build_bones_list` → `.bmap` 로드)
3. 액션별 `bpy.ops.arp.retarget()` 실행

## 프로필 시스템

### 구조
```json
{
  "arp_preset": "dog",
  "deform_to_ref": {
    "소스본이름": "ARP_ref_본이름"
  },
  "mirror_suffix": { "source": ["_L","_R"], "arp": [".l",".r"] },
  "ref_alignment": { "priority": {}, "avg_lr": {} }
}
```

- L사이드만 정의 → R사이드 자동 미러링
- `priority`: 여러 소스 본 중 우선 선택 (예: root_ref.x ← center 또는 root)

### ARP dog 프리셋 ref 본 매핑 (custom_quadruped)

| 부위 | 소스 본 | ARP ref 본 |
|------|---------|-----------|
| 루트 | root, center, pelvis | `root_ref.x` |
| 스파인 | spine01 | `spine_01_ref.x` |
| 스파인 | spine02 | `spine_02_ref.x` |
| 가슴 | chest | `spine_03_ref.x` |
| 목 | neck | `neck_ref.x` |
| 머리 | head | `head_ref.x` |
| **뒷다리** (leg 역할 3본) | thigh_L | `thigh_b_ref.l` |
| | leg_L | `thigh_ref.l` |
| | foot_L | `leg_ref.l` |
| **뒷발** (foot 역할) | toe_L | `foot_ref.l` |
| | toe tip 또는 virtual toe | `toes_ref.l` |
| **앞다리** (leg 역할 3본) | shoulder_L (시작본) | `thigh_b_ref_dupli_001.l` |
| | upperarm_L | `thigh_ref_dupli_001.l` |
| | arm_L | `leg_ref_dupli_001.l` |
| **앞발** (foot 역할) | hand_L | `foot_ref_dupli_001.l` |
| | hand tip 또는 virtual toe | `toes_ref_dupli_001.l` |
| 꼬리 | tail_01~04 | `tail_00~03_ref.x` |
| 턱 | jaw | `jaw_ref.x` |
| 눈 | eye_L | `c_eye_ref.l` |
| 귀 | ear01_L, ear02_L | `ear_01_ref.l`, `ear_02_ref.l` |

### 주의사항
- dog 프리셋은 3-bone leg 모드 사용 → ref 본에 `_b_` 접미사 (예: `thigh_b_ref.l`)
- 앞다리는 `_dupli_001` 접미사 추가 (예: `thigh_b_ref_dupli_001.l`)
- `leg` 역할 본이 3개면 ARP도 `thigh_b_ref → thigh_ref → leg_ref` 3본으로 고정
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할 생성 (virtual toe)
- face rig 불필요 — ear/eye/jaw만 사용, 나머지는 FBX 익스포트에서 제외
- `c_eye_ref`는 `c_` 접두사 있음
- ear ref는 `.l`/`.r`만 존재 (`.x` 없음)

## 리그 타입별 프로필 (계획)

| 프로필 | 대상 | 상태 |
|--------|------|------|
| `custom_quadruped.json` | Fox, Cat, Wolf 등 커스텀 사족보행 | 작업 중 |
| `rigify_quadruped.json` | Rigify DEF- 기반 사족보행 | 미작성 |
| `bird.json` | 조류 (Eagle, Pelican 등) | 미작성 |

## 파이프라인 스크립트

| 스크립트 | 역할 | 실행 환경 |
|----------|------|-----------|
| `01_create_arp_rig.py` | ARP 리그 생성 | Blender 내부 |
| `02_retarget_animation.py` | 애니메이션 리타게팅 | Blender 내부 |
| `pipeline_runner.py` | 01+02 순차 실행 래퍼 | Blender 내부 (--background) |
| `03_batch_convert.py` | 배치 처리 | Python (Blender 외부) |
| `arp_utils.py` | 공유 유틸리티 | Blender 내부 |

### 배치 처리 사용법
```
python scripts/03_batch_convert.py                    # dry-run (대상 목록)
python scripts/03_batch_convert.py --run              # 전체 실행
python scripts/03_batch_convert.py --run --filter normal/fox  # 폴더 필터
python scripts/03_batch_convert.py --run --workers 2  # 병렬 처리
```

## 현재 상태

- [x] Phase 0: ARP 오퍼레이터 파라미터 조사
- [x] 2단계 스크립트 분리 (01 + 02)
- [x] JSON 프로필 시스템 구축
- [x] custom_quadruped 프로필 ref 본 이름 수정
- [x] auto_scale 컨텍스트 버그 수정 (select_only 누락)
- [x] 에러 진단 강화 (run_arp_operator)
- [x] .bmap 자동 설치 (install_bmap_preset)
- [x] 배치 처리 시스템 (pipeline_runner + 03_batch_convert)
- [ ] Fox 파일 end-to-end 테스트 (Blender에서 실행)
- [ ] 추가 프로필 작성 (Rigify, 조류)
- [ ] .bmap 스파인 매핑 검토 (chest 본 누락)
