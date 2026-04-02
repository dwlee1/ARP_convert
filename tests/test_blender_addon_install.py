import importlib.util
from pathlib import Path

import arp_utils as au


def _load_installer_module():
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "tools" / "install_blender_addon.py"
    spec = importlib.util.spec_from_file_location("install_blender_addon", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_project_root_supports_repo_scripts_layout(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (repo_root / "mapping_profiles").mkdir()

    assert au.resolve_project_root(scripts_dir) == str(repo_root)


def test_resolve_project_root_supports_installed_package_layout(tmp_path):
    package_root = tmp_path / "arp_rig_convert"
    package_root.mkdir()
    (package_root / "mapping_profiles").mkdir()
    (package_root / "remap_presets").mkdir()

    assert au.resolve_project_root(package_root) == str(package_root)


def test_build_package_creates_installable_layout(tmp_path):
    installer = _load_installer_module()

    package_dir = installer.build_package(tmp_path)
    zip_path = installer.build_zip(package_dir, tmp_path, "4.5")

    assert (package_dir / "__init__.py").exists()
    assert (package_dir / "arp_utils.py").exists()
    assert (package_dir / "skeleton_analyzer.py").exists()
    assert (package_dir / "weight_transfer_rules.py").exists()
    assert (package_dir / "mapping_profiles").is_dir()
    assert (package_dir / "remap_presets").is_dir()
    assert zip_path.exists()
