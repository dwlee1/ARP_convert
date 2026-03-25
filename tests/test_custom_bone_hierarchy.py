import skeleton_analyzer as sa


class TestCustomBoneHierarchy:
    def test_order_bones_by_hierarchy_parent_first(self):
        bone_data = {
            "jaw": {"parent": "head"},
            "food": {"parent": "jaw"},
            "eye_l": {"parent": "head"},
        }

        ordered = sa.order_bones_by_hierarchy(["food", "jaw", "eye_l"], bone_data)

        assert ordered == ["jaw", "food", "eye_l"]

    def test_generate_bmap_content_orders_unmapped_by_hierarchy(self):
        analysis = {
            "chains": {},
            "unmapped": ["food", "jaw", "eye_l"],
            "bone_data": {
                "jaw": {"parent": "head"},
                "food": {"parent": "jaw"},
                "eye_l": {"parent": "head"},
            },
        }

        content = sa.generate_bmap_content(analysis)
        # 커스텀 본은 원본 이름 유지 (cc_ 접두사 없음)
        custom_lines = [
            line
            for line in content.splitlines()
            if line.endswith("%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%")
        ]

        assert custom_lines == [
            "jaw%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%",
            "food%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%",
            "eye_l%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%",
        ]

    def test_build_preview_parent_overrides_keeps_original_custom_hierarchy(self):
        original_bone_data = {
            "head": {"parent": "neck"},
            "jaw": {"parent": "head"},
            "food": {"parent": "jaw"},
            "foot": {"parent": "leg"},
        }

        overrides = sa.build_preview_parent_overrides(
            ["jaw", "food"],
            original_bone_data,
        )

        assert overrides == {
            "jaw": "head",
            "food": "jaw",
        }

    def test_build_preview_parent_overrides_keeps_top_level_custom_bone_rootless(self):
        original_bone_data = {
            "food": {"parent": None},
            "foot": {"parent": "leg"},
        }

        overrides = sa.build_preview_parent_overrides(
            ["food"],
            original_bone_data,
        )

        assert overrides == {
            "food": None,
        }
