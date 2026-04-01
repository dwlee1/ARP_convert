# F11 normalize_clean_hierarchy — 코덱스 인수인계 문서

> 작성: 2026-04-01, HEAD: `a1e2316`

## 1. 배경

동물 캐릭터 리그를 ARP(Auto-Rig Pro, dog preset)로 통일하는 프로젝트.
원본 아마추어를 FBX(Deform Only)로 익스포트 → 재임포트한 clean armature를 소스로 사용하여 ARP 네이티브 retarget을 수행한다.

**F11**은 이 clean armature의 3가지 문제를 해결하는 정규화 단계:
1. FBX deform-only 익스포트 시 non-deform 부모 본 제거 → 하이어라키 끊김
2. 웨이트 0 deform 본이 불필요하게 포함
3. FBX round-trip 시 rest pose가 frame 1 포즈로 오염

## 2. 현재 파이프라인

```
원본 아마추어
  ↓ extract_bone_data(preview_obj)  →  bone_data (world-space head/tail/roll)
  ↓
export_clean_fbx(source_obj)        →  FBX (deform only + baked anim)
  ↓
import_clean_fbx(fbx_path)          →  clean armature
  ↓
normalize_clean_hierarchy(clean_obj, bone_data)   ← F11 핵심
  │ Step A: keep/delete 본 분류
  │ Step B: NLA strip으로 액션별 씬 월드 행렬 기록
  │ Step C: Edit Mode → 플랫(부모 제거) + rest pose 교정 + 삭제
  │ Step D: 교정된 rest 기준으로 전체 본 리베이크
  ↓
clean armature (플랫, rest pose 교정됨, 리베이크된 애니메이션)
  ↓
ARP retarget (.bmap → build_bones_list → retarget)
```

## 3. 관련 파일

| 파일 | 역할 |
|------|------|
| `scripts/arp_utils.py` | `normalize_clean_hierarchy()`, `export_clean_fbx()`, `import_clean_fbx()` |
| `scripts/arp_convert_addon.py` | RemapSetup (line ~2877)에서 normalize 호출 |
| `scripts/pipeline_runner.py` | pipeline에서 normalize 호출 (line ~403) |
| `scripts/skeleton_analyzer.py` | `extract_bone_data()` (line 231), `preview_to_analysis()` (line 2220) |

## 4. 현재 코드 상태 (HEAD: a1e2316)

### `normalize_clean_hierarchy()` (arp_utils.py:266)

**Step A**: bone_data에 있으면 keep, 없으면 delete

**Step B** (NLA strip 기반 행렬 기록):
- 기존 NLA 트랙 전부 뮤트 + `anim_data.action = None`
- 각 액션마다 임시 NLA 트랙/스트립 생성 → depsgraph 평가 → `obj_world @ pb.matrix` 기록 → 트랙 제거
- try/finally로 NLA 복원 보장

**Step C** (Edit Mode):
- 모든 본의 부모 제거 (플랫)
- bone_data의 head/tail/roll로 rest pose 교정: `clean_world_inv @ Vector(bd["head"])`
- delete 본 제거

**Step D** (리베이크):
- 변환 체인: `obj_world_inv @ scene_world_mat → armature_mat`, `rest_inv @ armature_mat → local_mat`
- loc/rot(quaternion)/scale 분해 → FCurve 키프레임 삽입

### `export_clean_fbx()` (arp_utils.py:198)
- `use_armature_deform_only=True`, `bake_anim=True`, `bake_anim_use_all_actions=True`
- constraint/driver 뮤트 **하지 않음** (bake_anim이 뮤트 상태로 베이크하면 애니메이션 깨짐)

## 5. 해결된 문제

| 커밋 | 문제 | 해결 |
|------|------|------|
| `57c7069` | 부모-자식 개별 리베이크 시 부모의 FCurve 삭제 상태에서 자식 변환 계산 꼬임 | 플랫 하이어라키로 전환 (부모 간섭 원천 제거) |
| `9fbf722` | FBX rest pose가 frame 1 포즈로 오염 | bone_data의 원본 head/tail/roll로 임포트 후 교정 |
| `0d254ff` | NLA 트랙이 활성이면 action 전환 시 블렌딩 간섭 | NLA 뮤트 후 기록 |
| `c885516` | rest pose 교정 전후 armature-space 정의 불일치 | 씬 월드 좌표 기준 기록 + `obj_world_inv` 변환 체인 |
| `a1e2316` | Blender 4.5 Action Slot 없는 액션이 평가 안 됨 | NLA strip 기반 평가로 Slot 의존성 제거 |

## 6. ❌ 현재 미해결 문제: 다중 액션 리베이크

### 증상
- 기본 선택된 액션의 rest pose + 애니메이션은 정상
- **다른 액션들의 리베이크가 여전히 이상함**

### 시도한 방법과 결과

1. `animation_data.action = action` 전환 + NLA 뮤트 → **실패** (기본 액션만 작동)
2. `_assign_action_with_slot()` 슬롯 자동 할당 → **실패** (Blender 4.5 API 불일치)
3. 임시 NLA strip으로 각 액션 평가 → **실패** (여전히 안 됨)

### 가능한 원인 (미검증)

1. **NLA strip 생성 방식 문제**: `strips.new()` 호출 시 Blender 4.5에서 slot 바인딩이 필요할 수 있음
2. **depsgraph 캐싱**: 임시 트랙 생성/제거 사이에 depsgraph가 제대로 갱신되지 않음
3. **FCurve 직접 읽기 방식으로 전환 필요**: depsgraph 평가 대신 `action.fcurves`에서 직접 값 읽기
4. **Blender 4.5 NLA + Action Slot 상호작용**: NLA strip도 내부적으로 slot을 요구할 수 있음

### 추천 조사 방향

**방법 A: FCurve 직접 읽기 (depsgraph 우회)**
```python
for fc in action.fcurves:
    val = fc.evaluate(frame)  # 슬롯/NLA 무관하게 직접 값 읽기
```
- FCurve에서 bone의 loc/rot/scale 직접 읽기
- rest pose 행렬과 결합하여 armature-space 행렬 재구성
- 부모가 있는 하이어라키에서는 parent chain 순회 필요 (복잡)
- **플랫이 아닌 원본 하이어라키 상태에서** 읽어야 함 (Step B 시점)

**방법 B: Blender 4.5 Action Slot API 정확한 확인**
- Blender 4.5 Python 콘솔에서 `dir(action.slots[0])`, `dir(anim_data)` 실행하여 실제 API 확인
- `action.slots.new()` 대신 `action.slot_for_id()` 등 다른 메서드 존재 여부 확인

**방법 C: 별도 진단 스크립트**
```python
# Blender 콘솔에서 실행하여 각 방법의 동작 여부 확인
for action in bpy.data.actions:
    print(action.name, len(action.slots) if hasattr(action, 'slots') else 'N/A')
    for slot in getattr(action, 'slots', []):
        print(f'  slot: {slot.identifier}, handle: {slot.handle}')
```

## 7. Step D 리베이크의 추가 주의사항

Step D에서 `clean_obj.animation_data.action = action` 후 FCurve를 직접 삽입하는데, Blender 4.5에서 **슬롯 없이 FCurve 쓰기가 가능한지**도 확인 필요. 만약 슬롯이 없으면 FCurve 삽입 자체가 무시될 수 있음.

## 8. 기타 완료된 기능 (이번 세션)

| 기능 | 파일 | 상태 |
|------|------|------|
| Step 2 부모 편집 UI | arp_convert_addon.py | ✅ 커밋 `6c4a5aa` |
| ARPCONV_OT_SetParent 오퍼레이터 | arp_convert_addon.py:1438 | ✅ |
| pending_parent prop_search 드롭다운 | arp_convert_addon.py:3374 | ✅ |

## 9. 코드 위치 빠른 참조

```
arp_utils.py:198   export_clean_fbx()
arp_utils.py:236   import_clean_fbx()
arp_utils.py:266   normalize_clean_hierarchy()  ← F11 핵심
arp_utils.py:461   _collect_actions()
arp_utils.py:478   _norm_fc_insert()

arp_convert_addon.py:2827  analysis = preview_to_analysis(preview_obj)
arp_convert_addon.py:2868  clean_obj, fbx_path = create_clean_source(source_obj)
arp_convert_addon.py:2879  normalize_clean_hierarchy(clean_obj, analysis.get("bone_data", {}))

skeleton_analyzer.py:231   extract_bone_data()  — head/tail은 world-space 튜플
skeleton_analyzer.py:2220  preview_to_analysis() → bone_data = extract_bone_data(preview_obj)
```

## 10. 테스트

- `pytest tests/ -v` → 84개 전부 통과 (Blender 없이 실행 가능한 단위 테스트)
- Blender 실제 테스트는 수동 (addon의 Step 1~3.5 → Remap Setup → 애니메이션 확인)
