---
name: sync-addon
description: Blender 애드온 파일을 addons 폴더에 하드 링크로 동기화. /sync-addon 으로 실행. 파일 수정 후 하드 링크가 깨졌을 때, 블렌더 애드온 동기화가 필요할 때, "하드 링크", "블렌더 동기화", "애드온 연결", "sync addon" 등을 언급할 때 사용.
---

# Blender 애드온 하드 링크 동기화

프로젝트의 스크립트 파일을 Blender addons 폴더에 하드 링크로 연결하여, 프로젝트에서 수정하면 블렌더에서도 즉시 반영되도록 한다.

## 왜 하드 링크인가

- 복사(cp)는 원본과 별개 파일이 되어 수정 시 매번 재복사 필요
- 심링크는 Windows에서 관리자 권한이 필요할 수 있음
- 하드 링크는 같은 파일을 가리키므로 어느 쪽에서 수정해도 즉시 반영

## 주의: Edit 도구가 하드 링크를 깨뜨림

Claude Code의 Edit 도구는 파일을 수정할 때 새 파일로 교체하는 방식을 사용한다. 이 때문에 원본 파일의 inode가 바뀌면서 하드 링크가 끊어진다. 파일 수정 후에는 반드시 이 스킬을 다시 실행해야 한다.

## 실행 절차

1. 동기화 대상 파일 결정:
   - 기본값: `scripts/arp_convert_addon.py`, `scripts/skeleton_analyzer.py`, `scripts/arp_utils.py`
   - 사용자가 특정 파일을 지정하면 해당 파일만 처리

2. Blender addons 경로 탐색:
   - Windows: `%APPDATA%/Blender Foundation/Blender/*/scripts/addons/`
   - 여러 버전이 있으면 가장 높은 버전 사용

3. 동기화 대상 경로 (두 곳 모두 처리):
   - **단일 파일 경로**: `addons/arp_convert_addon.py`, `addons/arp_utils.py`, `addons/skeleton_analyzer.py`
   - **패키지 폴더 경로**: `addons/arp_rig_convert/__init__.py` (← `arp_convert_addon.py`), `addons/arp_rig_convert/arp_utils.py`, `addons/arp_rig_convert/skeleton_analyzer.py`
   - Blender가 어느 쪽을 로드할지 모르므로 **양쪽 모두** 하드 링크해야 한다
   - 패키지 폴더가 존재하지 않으면 스킵 (단일 파일만 처리)

4. 각 파일에 대해:
   - 프로젝트 파일과 addons 파일의 inode 비교 (`stat` 명령)
   - inode가 같으면 "이미 연결됨" 출력하고 스킵
   - inode가 다르거나 addons에 파일이 없으면:
     - addons 쪽 파일 삭제 (있는 경우)
     - 하드 링크 생성: `ln <프로젝트파일> <addons경로>`
   - 결과 검증: 양쪽 inode + Links 수 확인
   - 패키지 폴더의 `__pycache__/` 삭제 (캐시된 구버전 바이트코드 제거)

5. 결과를 테이블로 출력:
   ```
   | 파일 | 대상 | 상태 | Inode | Links |
   ```

## 명령어 참고

```bash
# inode 확인
stat <파일> | grep "Inode"

# 하드 링크 생성 (Windows Git Bash)
ln <원본> <대상>

# addons 경로 예시 (Git Bash 형식)
/c/Users/manag/AppData/Roaming/Blender Foundation/Blender/4.5/scripts/addons/
```
