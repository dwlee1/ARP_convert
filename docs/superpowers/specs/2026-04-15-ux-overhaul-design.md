# ARP Convert 애드온 UX 전면 개선 설계

**날짜**: 2026-04-15
**범위**: 색상 체계, 역할 UI, 서브패널 구조, 언어 통일, 뷰포트 하이라이트
**타겟 사용자**: 팀/소규모 스튜디오 (한국어 중심)

## 배경 및 문제

현재 애드온은 기능적으로 완성되어 있으나, 상용 수준의 UX에 미치지 못한다.
핵심 문제 3가지:

1. **프리뷰 본 역할 구분 부족** — spine/neck/head가 동일 파랑, leg/foot 명도 차이만, L/R 구분 없음
2. **부모-자식 관계 파악 어려움** — 뷰포트에서 부모 추적 불가, 트리에서 들여쓰기만으로 계층 파악 어려움
3. **역할 지정 UI 불명확** — BLeg/FLeg/BFoot 약어 의미 불분명, UI 색상과 뷰포트 본 색상 불일치

## 1. 색상 팔레트 재설계

### 원칙

- 각 역할에 고유 색상 부여 (중복 제거)
- L/R: 왼쪽 = 원색(진한 톤), 오른쪽 = 밝은 톤
- leg/foot: 같은 계열 내에서 색조 이동으로 구분 (빨강→자홍, 초록→청록)
- UI 버튼 색상과 뷰포트 본 색상 동일

### 새 팔레트

| 역할 | RGB | 설명 |
|------|-----|------|
| root | (1.0, 0.82, 0.0) | 노랑 |
| trajectory | (0.71, 0.63, 0.24) | 올리브 |
| spine | (0.24, 0.39, 0.86) | 파랑 (진) |
| neck | (0.31, 0.55, 1.0) | 파랑 (중) |
| head | (0.51, 0.67, 1.0) | 파랑 (연) |
| back_leg_l | (0.86, 0.24, 0.24) | 빨강 |
| back_leg_r | (1.0, 0.43, 0.43) | 밝은 빨강 |
| back_foot_l | (0.71, 0.16, 0.27) | 자홍 |
| back_foot_r | (0.86, 0.35, 0.47) | 밝은 자홍 |
| front_leg_l | (0.20, 0.71, 0.20) | 초록 |
| front_leg_r | (0.39, 0.86, 0.39) | 밝은 초록 |
| front_foot_l | (0.12, 0.51, 0.24) | 청록 |
| front_foot_r | (0.27, 0.67, 0.39) | 밝은 청록 |
| ear_l | (0.0, 0.75, 0.78) | 시안 |
| ear_r | (0.31, 0.86, 0.90) | 밝은 시안 |
| tail | (0.94, 0.59, 0.12) | 주황 |
| unmapped | (0.43, 0.43, 0.43) | 회색 |

### 본 색상 적용

`pbone.color.palette = "CUSTOM"` + `pbone.color.custom`:
- **normal**: 역할 색상 (위 표)
- **select**: 역할 색상 + 밝기 0.3 증가
- **active**: 역할 색상 + 밝기 0.5 증가

변경 위치: `skeleton_detection.py`의 `ROLE_COLORS` 딕셔너리 + `arp_ops_preview.py`의 색상 적용 로직.

## 2. 역할 버튼 UI 개선

### 라벨 변경

약어를 한국어 풀네임으로 교체:

| 현재 | 개선 |
|------|------|
| BLeg L | 뒷다리 L |
| BLeg R | 뒷다리 R |
| FLeg L | 앞다리 L |
| FLeg R | 앞다리 R |
| BFoot L | 뒷발 L |
| BFoot R | 뒷발 R |
| FFoot L | 앞발 L |
| FFoot R | 앞발 R |
| Root | 루트 |
| Spine | 스파인 |
| Neck | 목 |
| Head | 머리 |
| Tail | 꼬리 |
| Ear L/R | 귀 L/R |
| Unmapped (cc_) | 미매핑 |
| Trajectory | 궤적 |

### 카테고리명

| 현재 | 개선 |
|------|------|
| Body: | 몸통: |
| Legs: | 다리: |
| Feet (★ bank/heel 자동 생성): | 발: (bank/heel 가이드 자동 생성) |
| Head: | 머리 부속: |

### 색상 매칭

Blender UI의 오퍼레이터 버튼은 텍스트 색상을 직접 지정할 수 없다. 유니코드 `●`를 넣어도 흰색으로만 표시된다.

**채택 방안: `bpy.utils.previews`로 역할별 색상 아이콘 생성**

- `register()` 시점에 각 역할의 색상으로 16×16 픽셀 사각형 아이콘을 프로그래밍 방식으로 생성
- `preview_collection.new(role_id)` → `image_pixels_float`에 해당 역할 RGB 채워넣기
- 역할 버튼에 `icon_value=preview_collection[role_id].icon_id` 전달
- `unregister()` 시 `bpy.utils.previews.remove()` 정리

이 방식은 Blender 애드온에서 흔히 사용되는 패턴이며, 뷰포트 본 색상과 정확히 일치하는 색상 아이콘을 버튼에 표시할 수 있다.

변경 위치: `arp_ui.py`의 역할 버튼 섹션, `arp_ops_roles.py`의 `ROLE_ITEMS`.

## 3. 계층 트리 개선

### 트리 연결선

현재 들여쓰기만으로 계층을 표시하는 것을 트리 연결선 문자로 교체:

```
● Root 루트
├─ ● Spine1 스파인
│  └─ ● Spine2 스파인
│     └─ ● Neck 목
│        └─ ● Head 머리
├─ ○ Hip_L 미매핑
│  └─ ● Thigh_L 뒷다리 L
│     └─ ● Shin_L 뒷다리 L
│        └─ ● Foot_L 뒷발 L
```

### 구현

- `_populate_hierarchy_collection()`에서 각 본의 `is_last_child` 플래그를 추가 계산
- 트리 표시 시 `depth`와 `is_last_child` 조합으로 `├─` / `└─` / `│` 문자 결정
- `ARPCONV_HierarchyBoneItem`에 `tree_prefix` StringProperty 추가 — 미리 계산된 연결선 문자열 저장

### 색상 아이콘 + 역할 라벨

- 역할 버튼과 동일한 `bpy.utils.previews` 색상 아이콘을 트리 항목에도 `icon_value`로 적용
- 본 이름 뒤에 역할 한국어 라벨 병기 (예: `"Thigh_L  뒷다리 L"`)
- 미매핑 본: 회색 아이콘, 제외(w=0) 본: `RADIOBUT_OFF` 기본 아이콘 유지

변경 위치: `arp_ui.py`의 hierarchy 표시 섹션, `arp_ops_preview.py`의 `_populate_hierarchy_collection()`.

## 4. 서브패널 구조

### 현재 → 개선

단일 `ARPCONV_PT_MainPanel` → 메인 패널 + 5개 서브패널 + 1개 도구 패널.

| 클래스 | bl_label | 내용 |
|--------|----------|------|
| `ARPCONV_PT_MainPanel` | "ARP 리그 변환" | 헤더 + 프로그레스 바 (버전 표시) |
| `ARPCONV_PT_Step1_Analysis` | "1. 분석" | 소스 선택, Create Preview 버튼, 신뢰도 |
| `ARPCONV_PT_Step2_Roles` | "2. 역할 수정" | Hierarchy 트리, 역할 버튼, 선택 정보, 부모 변경 |
| `ARPCONV_PT_Step3_Build` | "3. 리그 생성" | IK 슬라이더, Build Rig 버튼 |
| `ARPCONV_PT_Step4_Retarget` | "4. 리타겟" | Setup, 본 매핑 UIList, Execute |
| `ARPCONV_PT_Step5_Cleanup` | "5. 정리" | Cleanup 버튼 |
| `ARPCONV_PT_Tools` | "도구" | Regression fixture/report |

### 서브패널 설정

모든 서브패널: `bl_parent_id = "ARPCONV_PT_main"`, `bl_space_type = "VIEW_3D"`, `bl_region_type = "UI"`, `bl_category = "ARP Convert"`.

### 자동 접힘/펼침

- `bl_options = {'DEFAULT_CLOSED'}`: Step 3~5, 도구
- `bl_options = set()` (기본 펼침): Step 1~2

### 진행 상태 표시

각 서브패널의 `draw_header(self, context)`에서 상태 아이콘 표시:

| 상태 | 아이콘 | 조건 |
|------|--------|------|
| 완료 | `CHECKMARK` | props 기반 판별 (예: `is_analyzed`, Build 완료 플래그) |
| 현재 | `PLAY` | 현재 작업 단계 자동 판별 |
| 대기 | `RADIOBUT_OFF` | 아직 도달하지 않음 |

### 요약 정보

접힌 상태에서도 `draw_header()`에 핵심 수치를 표시:
- Step 1: "신뢰도 87%"
- Step 2: "12/18 매핑됨"
- Step 3: (완료 시) "✓"
- Step 4: (본 매핑 수)

### 필요한 추가 프로퍼티

`ARPCONV_Props`에 추가:
- `build_completed: BoolProperty` — Build Rig 완료 여부
- `retarget_setup_done: BoolProperty` — Retarget Setup 완료 여부
- `mapped_bone_count: IntProperty` — 매핑된 본 수 (캐시)
- `total_bone_count: IntProperty` — 전체 본 수 (캐시)

변경 위치: `arp_ui.py` (패널 분리), `arp_props.py` (프로퍼티 추가), `arp_convert_addon.py` (클래스 등록).

## 5. 뷰포트 부모 체인 하이라이트

### 동작

1. 프리뷰 아마추어에서 본 선택 시, 선택 본 → 루트까지 부모 체인을 자동 추적
2. 체인에 속한 본들의 `bone.select = True` 설정 → select 색상(밝은 톤)으로 표시
3. 선택 해제 시 원래 상태 복원

### 구현

- `bpy.app.handlers.depsgraph_update_post`에 핸들러 등록
- 핸들러는 활성 오브젝트가 프리뷰 아마추어인 경우에만 동작
- 성능: 프리뷰 본은 최대 50~80개 수준이므로 매 업데이트에 체인 추적해도 부담 없음
- 핸들러 등록/해제는 `register()`/`unregister()`에서 관리

### 주의사항

- `depsgraph_update_post`는 빈번하게 호출되므로, 활성 오브젝트와 선택 상태가 변경된 경우에만 처리 (이전 선택 캐시와 비교)
- 사용자의 의도적 다중 선택(Shift+클릭)과 자동 체인 선택을 구분해야 함 → 체인 본은 `bone.select`만 설정하고 `bone.select_head`/`bone.select_tail`은 건드리지 않음

변경 위치: 새 모듈 `arp_viewport_handler.py` 또는 `arp_ops_preview.py`에 핸들러 추가.

## 6. 언어 통일 + 툴팁

### 한국어 통일 규칙

- 모든 UI 라벨, 카테고리명, 안내 텍스트: 한국어
- 예외: `bl_category` ("ARP Convert"), `bl_idname`, 내부 식별자 — 영어 유지
- `bl_info["description"]`: "프리뷰 기반 ARP 리그 자동 변환"

### 단계 제목 변경

| 현재 | 개선 |
|------|------|
| Step 1: 분석 | 1. 분석 |
| Step 2: 역할 수정 | 2. 역할 수정 |
| Step 3: Build Rig | 3. 리그 생성 |
| Step 4: Retarget | 4. 리타겟 |
| Step 5: Cleanup | 5. 정리 |

### 툴팁 추가

모든 프로퍼티에 `description` 필드 추가:

| 프로퍼티 | 툴팁 |
|----------|-------|
| source_armature | "변환할 원본 아마추어" |
| preview_armature | "생성된 프리뷰 아마추어" |
| confidence | "자동 역할 추론 신뢰도 (0~100%)" |
| front_3bones_ik | "앞다리 3본 IK 영향도. 0이면 어깨 독립 회전, 1이면 발 IK에 연동" |
| show_source_hierarchy | "소스 본 계층 트리 표시/숨김" |
| pending_parent | "선택한 본의 새 부모 — 선택 시 자동 적용" |

### 오퍼레이터 피드백

| 오퍼레이터 | 현재 | 개선 |
|-----------|------|------|
| Create Preview | report INFO | 서브패널 요약 "신뢰도 N%, M본 분석" |
| Set Role | report 한 줄 | "[역할명] → bone1, bone2 (N본 지정됨)" |
| Build Rig | report | 서브패널 ✓ 전환 + 소요 시간 |
| 에러 | WARNING | 서브패널 내 경고 박스 (ERROR 아이콘) |

변경 위치: `arp_props.py`, `arp_ops_preview.py`, `arp_ops_roles.py`, `arp_ops_build.py`, `arp_convert_addon.py`.

## 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `skeleton_detection.py` | ROLE_COLORS 팔레트 교체 |
| `arp_ui.py` | 단일 패널 → 서브패널 분리, 역할 버튼 라벨/색상, 트리 연결선 |
| `arp_props.py` | 프로퍼티 description 추가, 상태 프로퍼티 추가, HierarchyBoneItem 확장 |
| `arp_ops_preview.py` | 트리 구축 로직 수정, 핸들러 등록 |
| `arp_ops_roles.py` | ROLE_ITEMS 라벨 한국어화, 피드백 개선 |
| `arp_ops_build.py` | 완료 상태 플래그 설정 |
| `arp_convert_addon.py` | 서브패널 클래스 등록, bl_info 수정 |
| (신규) `arp_viewport_handler.py` | 뷰포트 부모 체인 하이라이트 핸들러 |

## 변경하지 않는 것

- 기능 로직 (분석, Build Rig, 리타겟 파이프라인)
- 데이터 구조 (analysis, roles, bone_pairs)
- 파이프라인 실행 경로 (addon, pipeline, batch)
- 커스텀 본 셰이프 (기본 옥타헤드론 유지)
