# Rabbit 구조 Baseline (경량)

**날짜**: 2026-04-17
**대상**: `Assets/5_Models/02. Animals/00.Rabbit/`
**BlenderRigConvert 커밋**: `de924b7aa1d8f8bbce53e07e76c303f29b6265c4`
**범위 한정**: Play mode 녹화/Console 경고 capture는 시간 비용으로 생략. 구조 baseline만 유지.

## FBX GUID 전수 (swap 후 변동 없어야 함)

| FBX | GUID |
|-----|------|
| rabbit_animation.fbx | f01ef593d9cf73a4e94a2ab37b4745c1 |
| Rabbit_DutchBrown.fbx | aef4bdb5ca354c449b892b7d42b320c1 |
| Animal_2002.fbx | 425206ccdace964488c86ce2937df18f |
| Animal_2011.fbx | 79caaf55f5d5b3249ab173da595f51ae |
| Animal_3161.fbx | bacb48f986e7b584390a10c2e6576967 |
| rabbit_CherryBlossom.fbx | 37d75ccbdf31bca40825932188f57539 |

참고: 동일 폴더의 `lopear_animation.fbx` (guid `be728792e9897304b9a0652ee890971a`)는 lopear 애셋이므로 Rabbit 파일럿 baseline에서 제외.

## AnimationClip fileID ↔ 이름 매핑 (Cleanup 후 유지되어야 함)

`rabbit_animation.fbx.meta` → `internalIDToNameTable:` 블록 전수 복사. Task 14 sandbox 반입 결과의 clip fileID와 비교하여 보존 여부 검증.

| fileID (int64) | Clip Name |
|----------------|-----------|
| -4055284855663334321 | Rabbit_dig |
| -8438407203743230057 | Armature\|Rabbit_idle |
| -6955810245249516388 | Armature\|Rabbit_jump |
| 4722112430157918280 | Armature\|Rabbit_jump(remove_Y) |
| 6282740208386744592 | Armature\|Rabbit_landing |
| 2259318888304712624 | Armature\|Rabbit_lookaround |
| -9178546838432071958 | Rabbit_runJump |
| 3917304941232476163 | Armature\|Rabbit_walk |
| -5745629922189365142 | Armature\|Rabbit_wash |
| -4551005270089556199 | Rabbit_idle |
| -7196996375264592756 | Rabbit_jump |
| -7694787021363270658 | Rabbit_jump(remove_Y) |
| -6449447709505211878 | Rabbit_landing |
| 4813876942005960582 | Rabbit_lookaround |
| -3748878328859994713 | Rabbit_run |
| 6173812369843160887 | Rabbit_walk |
| -231281761100502207 | Rabbit_wash |
| 143820807323742137 | Rabbit_eat |
| 2877670142546739676 | Rabbit_eat_start |
| 4682550846892719728 | Rabbit_eat_end |
| -8569508555272967342 | Rabbit_sleep |
| -3094600346173891965 | Rabbit_run_down(Y_remove) |
| 8819998969804782018 | Rabbit_run_jump(Y_remove) |
| -5964781211410773116 | Landmark_8_down |
| 3595646265062279545 | Landmark_8_lookaround |
| 68714083472746118 | Landmark_8_up |

**합계**: 26 clips (Armature|<name> prefix 있는 엔트리와 prefix 없는 엔트리가 공존 — Unity 측 takeName 정규화 전후 매핑으로 보임)
