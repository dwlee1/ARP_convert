# Rigify → AutoRig Pro 자동 변환 시스템 - 기술 상세 계획

> 작성일: 2026-03-18
> 프로젝트: BlenderRigConvert
> 환경: Blender 4.5 LTS + AutoRig Pro 애드온

---

## Context

프로젝트의 ~500개 Rigify 기반 .blend 파일을 ARP 리그로 변환해야 함. 기존 50%는 처음부터 ARP로 제작된 것이며, Rigify→ARP 변환은 한 번도 수행된 적 없음. 기존 애니메이션(키프레임 액션 다수, 80%+ 파일)을 보존하면서 변환하고, 최종적으로 FBX 익스포트가 성공해야 함.

기존 리그는 순수 Rigify가 아닌 경우도 있음 — 커스텀 본(꼬리, 귀 등) 추가 및 네이밍 혼재.

---

## 핵심 참조 자료

| 자료 | URL/경로 | 용도 |
|------|----------|------|
| ARP-Batch-Retargeting | https://github.com/Shimingyi/ARP-Batch-Retargeting | 배치 리타게팅 실제 코드 참조 |
| ARP 소스코드 | https://github.com/jasongzy/auto_rig_pro | 오퍼레이터 파라미터 확인 |
| AutoRigPro-to-Rigify | https://github.com/israelandrewbrown/AutoRigPro-to-Rigify | 150+ 본 매핑 테이블 역참조 |
| ARP Remap 공식 문서 | https://www.lucky3d.fr/auto-rig-pro/doc/remap_doc.html | Remap 워크플로우 |
| ARP Quick Rig 문서 | https://www.lucky3d.fr/auto-rig-pro/doc/quick_rig_doc.html | Quick Rig 대안 경로 |
| ARP 리그 데이터 형식 | `Sup_01/Frog/rigging_test/arp_Frog.py` | 본 위치 데이터 형식 참조 |
| Rigify 네이밍 문서 | https://developer.blender.org/docs/features/animation/rigify/utils/naming/ | DEF 본 네이밍 규칙 |

---

## 변환 대상 범위

**4족보행 동물 + 조류만 대상** (해양/기타 제외)

| 폴더 | 카테고리 | 예시 |
|------|----------|------|
| `normal/` | 사족보행 | Cat, Fox, Bear, Wolf |
| `bird/` | 조류 | Eagle, Pelican, Albatross |
| `Sup_01/`, `Sup_02/` | 혼합 | 해당 카테고리에 속하는 동물만 |
| `2024/`, `2025/`, `2026/` | 이벤트 | 해당 카테고리에 속하는 동물만 |

---

## 본 유형 분류

| 유형 | 예시 | 매핑 전략 |
|------|------|-----------|
| 표준 Rigify DEF 본 | `DEF-spine`, `DEF-upper_arm.L` | 이름 기반 매핑 → ARP 대응 본 |
| DEF- 커스텀 본 | `DEF-tail.001`, `DEF-ear.L` | 이름 시도 → 위치 기반 fallback |
| 독자적 네이밍 본 | `Tail_01`, `Ear_L` 등 | ARP 커스텀 본(`cc_` 접두사)으로 패스스루 |

**패스스루 전략**: 매핑 불가한 커스텀 본은 ARP 리그에 `cc_` 접두사로 추가하여 애니메이션 데이터 보존.

---

## 네이밍 차이점

| 항목 | Rigify | ARP |
|------|--------|-----|
| 좌/우 접미사 | `.L` / `.R` (대문자) | `.l` / `.r` (소문자) |
| 중앙 접미사 | 없음 | `.x` |
| 본 접두사 | `DEF-`, `ORG-`, `MCH-` | `c_` (컨트롤), `cc_` (커스텀) |
| 스파인 | `DEF-spine`, `.001`, `.002` | `spine_01_ref.x`, `spine_02_ref.x` |

---

## 접근 전략: 2가지 경로 병렬 검토

### 경로 A: Remap 기반 (권장)

```
Rigify 리그(소스) ──→ ARP Remap ──→ ARP 리그(타겟)
                      ↓
                  .bmap 매핑 파일
```

1. Rigify 리그를 소스 아마추어로 유지
2. ARP 리그를 타겟 아마추어로 추가 (`import_rig_data` 또는 `append_arp`)
3. `.bmap` 본 매핑 파일 생성 (Rigify DEF → ARP)
4. `bpy.ops.arp.retarget()` 으로 애니메이션 전송
5. 메시를 ARP에 리바인딩
6. Rigify 아마추어 제거

**장점**: ARP-Batch-Retargeting이라는 작동하는 코드 참조가 있음
**단점**: Rigify→ARP용 .bmap 파일을 새로 만들어야 함

### 경로 B: Quick Rig 기반 (대안)

1. Rigify DEF 본만 남긴 클린 스켈레톤 생성
2. ARP Quick Rig로 ARP 리그 자동 생성 (웨이트 보존)
3. Remap으로 애니메이션 전송

**장점**: Quick Rig가 리그 생성을 자동 처리
**단점**: Quick Rig가 동물 체형을 잘 처리하는지 미검증

→ **Phase 0에서 두 경로 모두 테스트하고 더 잘 되는 쪽으로 진행**

---

## Phase 0: 환경 조사 & 경로 결정

### 0-1. ARP 오퍼레이터 파라미터 조사

**생성할 파일:** `scripts/diagnose_arp_operators.py`

확인된 오퍼레이터:

```python
# ARP-Batch-Retargeting에서 확인된 실제 호출 패턴
bpy.ops.arp.auto_scale()                                    # 소스↔타겟 스케일 맞춤
bpy.ops.arp.build_bones_list()                              # 본 매핑 리스트 구축
bpy.ops.arp.import_config_preset(preset_name='xxx')         # .bmap 프리셋 로드
bpy.ops.arp.redefine_rest_pose()                            # 레스트 포즈 재정의
bpy.ops.arp.save_pose_rest()                                # 포즈를 레스트로 저장
bpy.ops.arp.retarget(frame_start=N, frame_end=M)           # 리타게팅 실행

# 추가 조사 필요
bpy.ops.arp.append_arp()          # ARP 리그 추가
bpy.ops.arp.import_rig_data()     # 리그 데이터 임포트 (arp_XXX.py)
bpy.ops.arp.match_to_rig()        # 레퍼런스→리그 생성
bpy.ops.arp.bind_to_rig()         # 메시 바인딩
bpy.ops.arp.batch_retarget()      # 배치 리타게팅
```

### 0-2. 본 매핑 테이블 기초 작업

AutoRigPro-to-Rigify 애드온에서 ARP→Rigify 매핑 150+개를 역참조하여 Rigify→ARP 매핑 초안 생성.

### 0-3. 테스트 파일 선정

`normal/` 폴더에서 가장 단순한 사족보행 동물 1개 선정 (Cat 또는 Fox).

### 사용자 액션
- Blender에서 진단 스크립트 실행 → 결과 공유

---

## Phase 1: PoC 스크립트 (단일 동물 변환)

### 생성할 파일
- `scripts/rigify_to_arp.py` — 단일 파일 변환 스크립트
- `scripts/bone_mapping.py` — 카테고리별 Rigify↔ARP 본 매핑
- `remap_presets/rigify_quadruped.bmap` — 사족보행용 매핑 프리셋

### 변환 파이프라인

```
 1. .blend 파일 열기
 2. Rigify 아마추어 식별 (DEF- 본 존재 여부)
 3. DEF 본 위치 추출 → ARP 레퍼런스 데이터 생성
 4. bpy.ops.arp.append_arp()       ← ARP 타겟 리그 추가
 5. bpy.ops.arp.import_rig_data()  ← 레퍼런스 본 배치
 6. bpy.ops.arp.match_to_rig()     ← ARP 리그 생성
 ─── 리그 생성 완료 ───
 7. 소스=Rigify, 타겟=ARP 설정
 8. bpy.ops.arp.build_bones_list()         ← 매핑 구축
 9. bpy.ops.arp.import_config_preset(...)  ← .bmap 로드
10. bpy.ops.arp.auto_scale()               ← 스케일 맞춤
11. bpy.ops.arp.retarget(...)              ← 리타게팅
 ─── 애니메이션 전송 완료 ───
12. bpy.ops.arp.bind_to_rig()  ← 메시 바인딩
13. Rigify 아마추어 제거
14. 저장
```

### 검증
- 변환 파일 열기 → 애니메이션 재생 비교
- `bpy.ops.arp_export_scene.fbx()` 로 FBX 익스포트

---

## Phase 2: 디버깅 & 보정

| 예상 이슈 | 원인 | 대응 |
|-----------|------|------|
| 축 방향 불일치 | Rigify/ARP 본 축 차이 | `redefine_rest_pose()` + 보정 매트릭스 |
| 본 개수 불일치 | 동물마다 스파인 세그먼트 다름 | 동적 매핑 (본 개수 감지 → 분할/병합) |
| 꼬리/귀/턱 매핑 누락 | 특수 본 | 카테고리별 확장 매핑 |
| 리타게팅 포즈 왜곡 | 레스트 포즈 차이 | `save_pose_rest()` 포즈 정렬 |
| 웨이트 손실 | 리바인딩 | ARP auto-weight 또는 기존 웨이트 전사 |
| 사이드 네이밍 (.L→.l) | 대소문자 차이 | 매핑 함수에서 자동 변환 |

---

## Phase 3: 조류 카테고리 확장

### 매핑 파일
```
remap_presets/
├── rigify_quadruped.bmap    # 사족보행
└── rigify_bird.bmap         # 조류
```

### 카테고리 자동 판별
```python
def detect_category(blend_path):
    if '/bird/' in path: return 'bird'
    if has_wing_bones(armature): return 'bird'
    return 'quadruped'
```

### 조류 특수 처리
- `bpy.ops.arp.align_wings()` 활용
- 날개 본: Rigify `DEF-wing.*` → ARP arm 계열 매핑

---

## Phase 4: 배치 처리 시스템

### 생성할 파일
- `scripts/batch_convert.py`

### 실행 흐름
```
1. blend_files_report.csv 로드 (이미 ARP인 파일 제외)
2. 파일별:
   a. 카테고리 자동 판별
   b. 해당 .bmap 프리셋 선택
   c. rigify_to_arp.py 로직 실행
   d. FBX 익스포트 테스트
   e. 결과 로깅
3. 최종 리포트 생성
```

### 실행 명령
```bash
blender --background --python scripts/batch_convert.py -- --input-csv blend_files_report.csv --output-dir converted/
```

### 안전장치
- 원본 파일 백업 (변환 전 .blend 복사)
- 실패 시 skip & 로그 (전체 배치 중단 방지)
- dry-run 모드 (실제 저장 없이 변환 가능성만 체크)

---

## 프로젝트 파일 구조

```
BlenderRigConvert/
├── scripts/
│   ├── diagnose_arp_operators.py    # Phase 0: ARP API 조사
│   ├── bone_mapping.py              # Rigify↔ARP 매핑
│   ├── rigify_to_arp.py             # 단일 파일 변환
│   └── batch_convert.py             # 배치 처리
├── remap_presets/
│   ├── rigify_quadruped.bmap        # 사족보행 매핑
│   └── rigify_bird.bmap             # 조류 매핑
├── docs/
│   ├── RigConversion_Plan_Summary.md
│   └── RigConversion_Plan_Technical.md
└── (기존 프로젝트 파일들...)
```

---

## 검증 체크리스트

- [ ] Phase 0: ARP 오퍼레이터 파라미터 전체 확보
- [ ] Phase 0: AutoRigPro-to-Rigify에서 매핑 테이블 역추출
- [ ] Phase 1: Cat/Fox 1마리 변환 성공
- [ ] Phase 1: 변환 파일 애니메이션 재생 정상
- [ ] Phase 1: FBX 익스포트 성공
- [ ] Phase 3: 조류 1마리 변환 성공
- [ ] Phase 4: 전체 배치 실행 → 성공률 90%+

---

## 리스크 매트릭스

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| ARP 오퍼레이터 context 문제 | 높음 | 치명적 | context override / ARP-Batch-Retargeting 코드 참조 |
| Rigify→ARP 본 매핑 불완전 | 높음 | 높음 | AutoRigPro-to-Rigify 역참조 + 위치 기반 fallback |
| 리타게팅 품질 저하 | 중간 | 높음 | `redefine_rest_pose()` + interactive tweaks |
| 동물별 스파인 세그먼트 불일치 | 중간 | 중간 | 동적 세그먼트 감지 매핑 |
| Quick Rig가 더 나은 경로일 수 있음 | 중간 | 낮음 | Phase 0에서 병렬 테스트 |

---

## 즉시 시작할 작업

1. `scripts/diagnose_arp_operators.py` 작성 — ARP 오퍼레이터 파라미터 전수 조사
2. AutoRigPro-to-Rigify GitHub 소스에서 본 매핑 테이블 추출
3. ARP-Batch-Retargeting의 `blender_retargeting.py` 분석 → 유스케이스 맞춤 개조 설계
