# Unity FBX ↔ Blender 원본 파일 매핑

> 자동 생성됨: `scripts/_oneoff_match_blend_inventory.py` 실행 결과 기반.
> 원본 데이터: [docs/MigrationInventory.csv](MigrationInventory.csv) `source_blend_hint` 컬럼.
> Blender 경로 기준: `Asset/Blender/` (`.gitignore` 됨 — 로컬 전용).

## 범례

- **Unity id**: Unity 프로젝트 내부 식별자
- **FBX 경로**: `Assets/5_Models/02. Animals/` 아래 상대 경로
- **Blender 경로**: `Asset/Blender/` 아래 상대 경로
- `???` — 자동 매칭 실패 (inventory에 대응 동물 없음 또는 수동 확인 필요)

## in_scope — 사족보행 22마리 (현재 이주 대상)

| Unity id | FBX 경로 | Blender 경로 |
|---|---|---|
| `BabyBear` | `17. Other_3000_3999/12_BabyBear/Baby_Bear_animation.fbx` | `normal/Baby_bear/Baby_Bear_animation.blend` |
| `BabyFox` | `17. Other_3000_3999/1_BabyFox/babyfox_animation.fbx` | `normal/baby_fox/blender/babyfox_animation_all_009.blend` |
| `BabyRabbit` | `17. Other_3000_3999/0_BabyRabbit/Baby_Rabbit_animation.fbx` | `normal/baby_rabbit/blender/Baby_Rabbit_animation.blend` |
| `BabyTurtle` | `17. Other_3000_3999/14_BabyTurtle/babyturtle_animation.fbx` | `sea/babyturtle/babyturtle_AllAni02.blend` |
| `BabyWolf` | `17. Other_3000_3999/10_Baby_wolf/Baby_Wolf_animation.fbx` | `2025/2025_Event Pass/2025_Baby_Red_Wolf/아기 붉은 늑대/Baby_Wolf_AllAni_250414.blend` |
| `Bear` | `03.Bear/bear_animation.fbx` | `normal/bear/blender/bear_AllAni_240311.blend` |
| `BlackCat` | `17. Other_3000_3999/15_Cat/BlackCat_animation.fbx` | `normal/Cat/Cat_Black/cat_black_AllAni04.blend` |
| `Capybara` | `17. Other_3000_3999/Capybara_animation.fbx` | `normal/capybara/blender/Capybara_animation_all.blend` |
| `Deer` | `04.Deer/deer_animation.fbx` | `normal/deer/blender/deer_AllAni_EX240311.blend` |
| `Fox` | `01.Fox/fox_animation.fbx` | `normal/fox/blender/fox_AllAni_240311.blend` |
| `Hedgehog` | `17. Other_3000_3999/Animal_Hadgehog/Hedgehog_animation.fbx` | `2026/2026_Event Pass/02월 발렌타인 패스/컨텐츠/초콜릿 고슴도치 4가지/Hedgehog_AllAni_EX260210.blend` |
| `Llama` | `08.Llama/Llama_animation.fbx` | `normal/Llama/blender/Llama_AllAni_250219.blend` |
| `Lopear` | `00.Rabbit/lopear_animation.fbx` | `normal/lopear/lopear_AllAni_EX240311.blend` |
| `Mole` | `17. Other_3000_3999/Animal_3015_mole/Mole_animation.fbx` | `normal/mole/Mole_animation.blend` |
| `Rabbit` | `00.Rabbit/rabbit_animation.fbx` | `normal/rabbit/blender/rabbit_AllAni_EX240311.blend` |
| `Raccoon` | `10.Raccoon/Raccoon_animation.fbx` | `normal/raccoon/blender/raccoon_AllAni_EX240311.blend` |
| `Sheep` | `09.Sheep/sheep_animation.fbx` | `normal/sheep/blender/sheep_AllAni_240311.blend` |
| `Squirrel` | `17. Other_3000_3999/Squirrel_Animation.fbx` | `normal/Squirrel/Squirrel_Animation.blend` |
| `Stag` | `04.Deer/stag_animation.fbx` | `normal/stag/blender/stag_AllAni_EX240311.blend` |
| `Turtle` | `06.Turtle/turtle_animation.fbx` | `sea/turtle/blender/turtle_animation2.blend` |
| `WhiteCat` | `17. Other_3000_3999/15_Cat/WhiteCat_animation.fbx` | `normal/Cat/Cat_White/cat_white_Allani03.blend` |
| `Wolf` | `05.Wolf/wolf_animation.fbx` | `normal/wolf/blender/wolf_AllAni_240311.blend` |

## out_of_scope — 24마리 (이주 대상 아님, 참고용)

새/해양/기타. 현재 이주 스코프에는 들어있지 않지만 향후 확장 시 참고.

| Unity id | FBX 경로 | Blender 경로 |
|---|---|---|
| `Albatross` | `20. NoSavedAnimal_4000/RewardedAds_3_Albatross/albatross_animation_all02.fbx` | `bird/albatross/albatross_Aniamtion2.blend` |
| `BabyDuck` | `17. Other_3000_3999/2_Baby_Duck/duckling_animation.fbx` | `normal/baby_duck/blender/duckling_animation_all.blend` |
| `BabyEagle` | `17. Other_3000_3999/7_baby_eagle/Baby_Eagle_animation.fbx` | `normal/Baby_bald_eagle/Baby_Eagle_animation.blend` |
| `BabyOrca` | `17. Other_3000_3999/13_BabyOrca/OrcaBaby_animation.fbx` | `sea/orca/babyOrca_AllAni02.blend` |
| `BaldEagle` | `11.Eagle/bald_eagle_animation.fbx` | `???` |
| `Clam` | `20. NoSavedAnimal_4000/RewardedAds_2_Clam/SourceFBX/Clam_animation_all01.fbx` | `sea/clam/blender/clam_animation_all01.blend` |
| `Crab` | `20. NoSavedAnimal_4000/RewardedAds_2_Clam/SourceFBX/Crab_animation_all01.fbx` | `???` |
| `Cuckoo` | `18. Bird_1000_1999/cuckoo/cuckoo_Animation.fbx` | `bird/cuckoo/blender/cuckoo_Animation.blend` |
| `Dolphin` | `15.Dolphin/dolphin_animation.fbx` | `sea/dolphin/blender/dolphin_rig(fix).blend` |
| `Duck` | `02.Duck/duck_animation.fbx` | `normal/duck/blender/duck_AllAni_240802.blend` |
| `EagleOwl` | `18. Bird_1000_1999/eagle_owl/eagle_owl_animation.fbx` | `bird/eagle owl/blender/eagle_owl_animation.blend` |
| `EarlessSeal` | `17. Other_3000_3999/Animal_EarlessSeal/seal_animation.fbx` | `???` |
| `Flamingo` | `13.Flamingo/flamingo_animation.fbx` | `normal/flamingo/blender/flamingo_animation6.blend` |
| `FlamingoV1` | `13.Flamingo/flamingo_animation_v1.fbx` | `???` |
| `Frog` | `17. Other_3000_3999/18_Frog/frog_animation.fbx` | `2026/2026_Event Pass/웹샵(엑솔라)/컨텐츠/민트 개구리/Frog_AllAni_260326.blend` |
| `FurSeal` | `07.Seal/furseal_Animation.fbx` | `sea/furseal/blender/furseal_Animation4.blend` |
| `HalloweenPass` | `17. Other_3000_3999/15_Cat/UI/HalloweenPassAnimation.fbx` | `???` |
| `Orca` | `16.Orca/Orca_animation.fbx` | `sea/orca/Orca_AllAni02.blend` |
| `Puffin` | `18. Bird_1000_1999/puffin/puffin_animation.fbx` | `bird/puffin/blender/puffin_animation.blend` |
| `RedFrog` | `17. Other_3000_3999/18_Frog/redfrog_animation.fbx` | `???` |
| `SeaGull` | `18. Bird_1000_1999/sea_gull/seagull_animation.fbx` | `bird/seagull/blender/seagull_animation.blend` |
| `Shellsand` | `20. NoSavedAnimal_4000/RewardedAds_2_Clam/SourceFBX/Shellsand_animation_all01.fbx` | `???` |
| `Sparrow` | `18. Bird_1000_1999/sparrow/sparrow_animation.fbx` | `bird/small/sparrow/blender/sparrow_animation2.blend` |
| `Swan` | `17. Other_3000_3999/11_Swan/swan_animation.fbx` | `normal/swan/blender/swan_animation.blend` |

## 미해결 (???)

| Unity id | scope | 원인 추정 |
|---|---|---|
| `BaldEagle` | out_of_scope | inventory에 `Eagle`만 있음 (Bald 구분 없음) |
| `Crab` | out_of_scope | inventory에 Crab 엔트리 없음 |
| `EarlessSeal` | out_of_scope | inventory에 `Seal`만 있음 (Earless 구분 없음) |
| `FlamingoV1` | out_of_scope | inventory는 `Flamingo`만 (V1 버전 구분 없음) |
| `HalloweenPass` | out_of_scope | 이벤트 패키지로 추정 (단일 동물 아님) |
| `RedFrog` | out_of_scope | inventory에 Red Frog 없음 (Frog/Mint/Pink/Christmas Frog만 존재) |
| `Shellsand` | out_of_scope | 장식/오브젝트로 추정 |

## 재생성 방법

`docs/MigrationInventory.csv` 가 업데이트되면 이 문서도 재생성해야 함.

```bash
python scripts/_oneoff_match_blend_inventory.py   # CSV 먼저 갱신
# 이 문서는 _oneoff_build_mapping_doc.py 로 재생성 (또는 수작업)
```