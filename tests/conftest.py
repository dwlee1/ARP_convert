"""
pytest 설정: bpy 모듈 mock으로 Blender 없이 skeleton_analyzer 테스트 가능.
"""

import os
import sys
from unittest.mock import MagicMock

# bpy를 mock으로 등록 (skeleton_analyzer.py의 import bpy 대응)
sys.modules["bpy"] = MagicMock()

# scripts/ 디렉토리를 import 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scripts_dir = os.path.join(project_root, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
