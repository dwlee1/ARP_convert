# Feature Plan v5 — Remap UI 통합

최종 수정: 2026-03-27

> 이 문서는 ARP Remap 본 매핑 편집 UI를 우리 애드온에 통합하는 설계·구현 계획을 정리한다.
> 전체 프로젝트 상태는 `docs/ProjectPlan.md` 참조.

---

## 배경

### 현재 문제

1. **리타게팅 매핑이 보이지 않음**: `generate_bmap_content()`가 소스→ARP 매핑을 자동 생성하지만, 사용자가 결과를 확인하거나 수정할 방법이 없다
2. **매핑 손실 확인 불가**: 체인 수 불일치(5본 spine → 3본 ARP)로 일부 본이 폐기되지만, 어떤 본이 빠졌는지 UI에서 알 수 없다
3. **ARP Remap 패널 분리**: 매핑 확인을 위해 ARP 패널을 별도로 열어야 하며, ARP 패널의 본 매핑 리스트는 프로그래밍으로 읽을 수 없다

### 접근 방법

ARP Remap 패널을 그대로 가져오는 것은 불가능하다 (내부 상태 비공개, 패널 임베딩 API 없음). 대신 **동일한 기능의 자체 UI**를 구현한다:

- `CollectionProperty`로 매핑 쌍 저장
- `UIList`로 Source Bones ↔ Target Bones 리스트 표시
- 분석 결과에서 자동 채움 → 사용자 수정 가능 → .bmap 생성 → ARP 리타게팅

---

## F9. Remap UI 통합

### 기능 요약

| 항목 | 내용 |
|------|------|
| 우선순위 | F4(IK 모드) 다음 |
| 난이도 | 중간 |
| 상태 | 설계 완료 |

### UI 목표

```
┌─ Step 3.5: Remap 설정 ─────────────────────┐
│                                              │
│  [Auto Map]  (분석 결과로 자동 매핑)          │
│                                              │
│  Source Bones       Target Bones      상태   │
│  ┌────────────────┬────────────────┬───────┐ │
│  │ Spine1         │ c_spine_01.x   │  ✓    │ │
│  │ (Spine2)       │ —              │  ⚠    │ │
│  │ Spine3         │ c_spine_02.x   │  ✓    │ │
│  │ (Spine4)       │ —              │  ⚠    │ │
│  │ Spine5         │ c_spine_03.x   │  ✓    │ │
│  │ Thigh_L        │ c_thigh_fk.l   │  ✓    │ │
│  │ Leg_L          │ c_leg_fk.l     │  ✓    │ │
│  │ ...            │ ...            │       │ │
│  └────────────────┴────────────────┴───────┘ │
│                                              │
│  매핑됨: 18/22   미매핑: 4                    │
│                                              │
│  ☑ IK 모드 리타게팅                           │
│  [Re-Target]                                 │
│                                              │
└──────────────────────────────────────────────┘
```

### 핵심 설계

#### 1. 데이터 모델

```python
class ARPCONV_BoneMapEntry(PropertyGroup):
    """개별 본 매핑 엔트리"""
    source_bone: StringProperty(name="Source Bone")
    target_bone: StringProperty(name="Target Bone")
    role: StringProperty(name="Role")           # spine, back_leg_l, ...
    is_mapped: BoolProperty(default=True)        # 매핑 여부
    is_root: BoolProperty(default=False)         # root 본 여부
    ik_enabled: BoolProperty(default=False)      # IK 플래그
    ik_pole: StringProperty(default="")          # IK pole 본 이름

class ARPCONV_Props(PropertyGroup):
    # ... 기존 프로퍼티 ...
    bone_map: CollectionProperty(type=ARPCONV_BoneMapEntry)
    bone_map_index: IntProperty(name="Active Index", default=0)
```

#### 2. 엔트리 유형

| 유형 | `is_mapped` | `target_bone` | UI 표시 |
|------|------------|---------------|---------|
| 매핑됨 | True | ARP 컨트롤러 이름 | 정상 (✓) |
| 폐기됨 | False | "" | 회색 + 경고 (⚠) |
| 커스텀 (cc_) | True | 소스 이름 = 타겟 이름 | 자기참조 |

#### 3. 오퍼레이터

| 오퍼레이터 | bl_idname | 기능 |
|-----------|-----------|------|
| Auto Map | `arp_convert.auto_map` | 분석 결과 + ARP 리그에서 매핑 자동 생성 |
| Retarget | `arp_convert.retarget` | (기존) bone_map → .bmap 변환 후 리타게팅 |

#### 4. UIList

```python
class ARPCONV_UL_BoneMap(UIList):
    """본 매핑 리스트"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if item.is_mapped:
            row = layout.row(align=True)
            row.prop(item, "source_bone", text="", emboss=False)
            row.label(text="→")
            row.prop(item, "target_bone", text="", emboss=False)
            if item.ik_enabled:
                row.label(text="", icon="CON_KINEMATIC")
        else:
            row = layout.row(align=True)
            row.alert = True
            row.label(text=f"({item.source_bone})")
            row.label(text="— 미매핑")
```

### Auto Map 로직

`ARPCONV_OT_AutoMap.execute()`:

1. `preview_to_analysis(preview_obj)` → analysis dict 획득
2. `discover_arp_ctrl_map(arp_obj)` → 실제 ARP 컨트롤러 이름 획득
3. 역할별 체인 순회:
   - `map_role_chain(role, source_bones, ctrl_bones)` → 매핑 dict
   - 매핑된 본 → `is_mapped=True` 엔트리 추가
   - 매핑에서 빠진 소스 본 → `is_mapped=False` 엔트리 추가 (폐기됨 표시)
4. unmapped 커스텀 본 → 자기참조 엔트리 추가
5. IK 모드 시 foot 역할 → `ik_enabled=True`, `ik_pole` 설정

**핵심**: 현재 `generate_bmap_content()`의 로직을 재사용하되, 결과를 .bmap 문자열이 아니라 `CollectionProperty`에 저장한다.

### Retarget 흐름 변경

**현재**:
```
Retarget 버튼 → generate_bmap_content() → .bmap 파일 쓰기 → ARP 리타게팅
```

**변경 후**:
```
Auto Map 버튼 → bone_map CollectionProperty 채움 (UI에 표시)
  ↓ 사용자가 확인/수정
Retarget 버튼 → bone_map → .bmap 문자열 변환 → .bmap 파일 쓰기 → ARP 리타게팅
```

### .bmap 변환 함수

```python
def bone_map_to_bmap(bone_map_collection):
    """CollectionProperty → .bmap 문자열 변환"""
    lines = []
    for entry in bone_map_collection:
        if not entry.is_mapped:
            continue  # 미매핑 본은 .bmap에 포함하지 않음
        flags = f"{'True' if entry.is_root else 'False'}%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%"
        lines.append(f"{entry.target_bone}%{flags}")
        lines.append(entry.source_bone)
        lines.append("True" if entry.is_root else "False")
        lines.append("True" if entry.ik_enabled else "False")
        lines.append(entry.ik_pole)
    return "\n".join(lines)
```

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `scripts/arp_convert_addon.py` | `ARPCONV_BoneMapEntry` PropertyGroup 추가, `ARPCONV_UL_BoneMap` UIList 추가, `ARPCONV_OT_AutoMap` 오퍼레이터 추가, `ARPCONV_OT_Retarget` 수정 (bone_map → .bmap), 패널 draw에 Step 3.5 추가 |
| `scripts/skeleton_analyzer.py` | `generate_bmap_content()` 유지 (pipeline_runner/batch 경로에서 사용), `populate_bone_map()` 함수 추가 (analysis → CollectionProperty 채움) |
| `scripts/pipeline_runner.py` | 변경 없음 (기존 `generate_bmap_content()` 경로 유지) |
| `scripts/03_batch_convert.py` | 변경 없음 |

### 기존 코드 호환성

- **addon 경로**: bone_map UI → .bmap 변환 → 기존 ARP 리타게팅 (새 경로)
- **pipeline/batch 경로**: `generate_bmap_content()` 직접 사용 (기존 경로 유지)
- `generate_bmap_content()`는 삭제하지 않음 — 비대화형 경로에서 계속 사용

### 사용자 워크플로우 변경

**현재**:
```
Step 1: 분석 → Step 2: 역할 수정 → Step 3: Build Rig + Retarget (한 번에)
```

**변경 후**:
```
Step 1: 분석
Step 2: 역할 수정
Step 3: Build Rig
Step 3.5: Remap 설정 (Auto Map → 확인/수정)
Step 4: Retarget
```

### 완료 기준 체크리스트

- [ ] `ARPCONV_BoneMapEntry` PropertyGroup 등록
- [ ] `ARPCONV_UL_BoneMap` UIList로 매핑 리스트 표시
- [ ] `ARPCONV_OT_AutoMap`이 분석 결과에서 bone_map 자동 채움
- [ ] 매핑된 본과 폐기된 본이 UI에서 구분 표시
- [ ] 사용자가 target_bone 드롭다운으로 매핑 수정 가능
- [ ] `bone_map_to_bmap()` 변환 → 기존 ARP 리타게팅 경로와 호환
- [ ] 커스텀 본(cc_) 자기참조 매핑 정상 표시
- [ ] IK 모드 시 foot 본 IK 플래그 정상 설정
- [ ] pipeline_runner / batch 경로는 기존대로 동작 (회귀 없음)
- [ ] 매핑 통계 표시 (매핑됨 N/M, 미매핑 K)

---

## 구현 순서

```
1. ARPCONV_BoneMapEntry PropertyGroup + Props 등록
2. ARPCONV_OT_AutoMap 오퍼레이터 (generate_bmap_content 로직 재사용)
3. ARPCONV_UL_BoneMap UIList 구현
4. 패널 draw에 Step 3.5 섹션 추가
5. ARPCONV_OT_Retarget 수정 (bone_map → .bmap 변환)
6. Blender 실제 테스트
```

---

## 기술적 참고

### ARP Remap 패널을 직접 가져올 수 없는 이유

1. **내부 상태 비공개**: ARP의 본 매핑 리스트는 씬 프로퍼티가 아닌 패널 내부 상태로 관리됨
2. **프로그래밍 API 없음**: 개별 본 매핑을 읽거나 수정하는 오퍼레이터가 없음
3. **패널 임베딩 불가**: Blender는 다른 애드온의 패널을 자신의 패널에 포함할 수 없음
4. **데이터 교환 방식**: `.bmap` 파일이 유일한 프로그래밍 인터페이스

### .bmap 포맷 (5줄 반복)

```
Line 1: {target_bone}%{is_root}%{space}%{loc_offset}%{rot_offset}%{scale}%{flag1}%{flag2}%
Line 2: {source_bone}
Line 3: {is_location_bone}  (True = root 본만)
Line 4: {ik_flag}            (True = IK 컨트롤러)
Line 5: {ik_pole_name}       (비어있으면 FK)
```
