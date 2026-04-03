---
name: cleanup
description: .blend1 백업 파일 정리하여 디스크 공간 확보
---

Blender가 자동 생성하는 .blend1 백업 파일을 찾아 정리합니다.

1. `cleanup_blend1.py` 스크립트를 실행합니다 (확인 모드).
2. 삭제 대상 파일 목록과 절약될 용량을 사용자에게 보여줍니다.
3. 사용자가 확인하면 `--yes` 플래그로 삭제를 진행합니다.

주의: 삭제 전 반드시 사용자에게 확인을 받으세요.

실행 명령:
```bash
# 미리보기 (삭제하지 않음)
cd $PROJECT_DIR && python cleanup_blend1.py

# 실제 삭제 (사용자 확인 후)
cd $PROJECT_DIR && python cleanup_blend1.py --yes
```
