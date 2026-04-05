"""
mcp_verify 순수 헬퍼 pytest.
"""

import pytest

import mcp_verify as mv

# ─────────────────────────────────────────────────────────────
# TestFilterPairsByRole
# ─────────────────────────────────────────────────────────────


class TestFilterPairsByRole:
    def _sample_pairs(self):
        # (src, tgt, is_custom) 형식
        return [
            ("DEF-thigh_L", "c_thigh_b.l", False),
            ("DEF-thigh_R", "c_thigh_b.r", False),
            ("DEF-toe_L", "c_foot_fk.l", False),
            ("DEF-eye_L", "DEF-eye_L", True),
        ]

    def _sample_target_to_role(self):
        return {
            "c_thigh_b.l": "back_leg_l",
            "c_thigh_b.r": "back_leg_r",
            "c_foot_fk.l": "back_foot_l",
            # DEF-eye_L은 target_to_role에 없음 → role=None
        }

    def test_none_filter_returns_all(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter=None)
        assert len(result) == 4
        assert result[0]["source"] == "DEF-thigh_L"
        assert result[0]["target"] == "c_thigh_b.l"
        assert result[0]["role"] == "back_leg_l"
        assert result[0]["is_custom"] is False

    def test_string_filter_exact_match(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter="back_leg_l")
        assert len(result) == 1
        assert result[0]["target"] == "c_thigh_b.l"

    def test_list_filter_multi_role(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(
            pairs, mapping, role_filter=["back_leg_l", "back_foot_l"]
        )
        assert len(result) == 2
        targets = {r["target"] for r in result}
        assert targets == {"c_thigh_b.l", "c_foot_fk.l"}

    def test_empty_pairs_returns_empty(self):
        result = mv.filter_pairs_by_role([], {}, role_filter=None)
        assert result == []

    def test_pair_with_unknown_target_has_none_role(self):
        pairs = [("DEF-eye_L", "DEF-eye_L", True)]
        mapping = {}
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter=None)
        assert len(result) == 1
        assert result[0]["role"] is None
        assert result[0]["is_custom"] is True


# ─────────────────────────────────────────────────────────────
# TestComputePositionStats
# ─────────────────────────────────────────────────────────────


class TestComputePositionStats:
    def test_empty_returns_zero_stats(self):
        result = mv.compute_position_stats([])
        assert result == {"min": 0.0, "max": 0.0, "mean": 0.0, "count": 0}

    def test_uniform_distances(self):
        result = mv.compute_position_stats([1.0, 1.0, 1.0])
        assert result["min"] == 1.0
        assert result["max"] == 1.0
        assert result["mean"] == 1.0
        assert result["count"] == 3

    def test_mixed_distances(self):
        result = mv.compute_position_stats([1.0, 2.0, 3.0])
        assert result["min"] == 1.0
        assert result["max"] == 3.0
        assert result["mean"] == 2.0
        assert result["count"] == 3

    def test_single_element(self):
        result = mv.compute_position_stats([5.0])
        assert result["min"] == 5.0
        assert result["max"] == 5.0
        assert result["mean"] == 5.0
        assert result["count"] == 1


# ─────────────────────────────────────────────────────────────
# TestFormatComparisonReport
# ─────────────────────────────────────────────────────────────


class TestFormatComparisonReport:
    def test_report_contains_pair_names(self):
        data = [
            {"src": "DEF-thigh_L", "arp": "c_thigh_b.l", "max_err": 0.0, "mean_err": 0.0}
        ]
        result = mv.format_comparison_report(data)
        assert "DEF-thigh_L" in result
        assert "c_thigh_b.l" in result

    def test_report_shows_max_error(self):
        data = [
            {"src": "A", "arp": "B", "max_err": 0.00364, "mean_err": 0.00200}
        ]
        result = mv.format_comparison_report(data)
        assert "0.00364" in result

    def test_empty_results_returns_fallback_text(self):
        result = mv.format_comparison_report([])
        assert result == "no pairs compared"


# ─────────────────────────────────────────────────────────────
# TestMatchBoneNames
# ─────────────────────────────────────────────────────────────


class TestMatchBoneNames:
    def test_none_pattern_returns_sorted_all(self):
        result = mv.match_bone_names(["b", "a", "c"], None)
        assert result == ["a", "b", "c"]

    def test_prefix_match(self):
        bones = ["c_thigh_b.l", "c_leg_fk.l", "c_thigh_b.r"]
        result = mv.match_bone_names(bones, r"^c_thigh_b")
        assert result == ["c_thigh_b.l", "c_thigh_b.r"]

    def test_regex_alternation(self):
        result = mv.match_bone_names(["alpha", "beta", "gamma"], r"^(alpha|gamma)$")
        assert result == ["alpha", "gamma"]

    def test_escape_dot(self):
        result = mv.match_bone_names(["c_thigh_b.l", "c_thigh_bxl"], r"^c_thigh_b\.l$")
        assert result == ["c_thigh_b.l"]

    def test_no_match_returns_empty(self):
        result = mv.match_bone_names(["a", "b"], r"^z")
        assert result == []
