import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import zh_variant_lexicon  # noqa: E402


class OpenCCWrapperTests(unittest.TestCase):
    def test_default_config_targets_simplified_to_taiwan_conversion(self):
        self.assertEqual(
            zh_variant_lexicon.DEFAULT_OPENCC_CONFIG,
            "s2twp",
        )

    def test_build_converter_uses_config_name(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            opencc_mock.OpenCC.return_value = mock.Mock()

            converter = zh_variant_lexicon.build_converter("s2twp")

        opencc_mock.OpenCC.assert_called_once_with("s2twp")
        self.assertIsNotNone(converter)

    def test_generate_opencc_candidate_uses_default_config_when_not_provided(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            converter = mock.Mock()
            converter.convert.return_value = "人工智慧系統依賴網路。"
            opencc_mock.OpenCC.return_value = converter

            candidate = zh_variant_lexicon.generate_opencc_candidate(
                "人工智能系統依賴网络。",
            )

        opencc_mock.OpenCC.assert_called_once_with("s2twp")
        self.assertEqual(candidate, "人工智慧系統依賴網路。")

    def test_generate_opencc_candidate_converts_text(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            converter = mock.Mock()
            converter.convert.return_value = "人工智慧系統依賴網路。"
            opencc_mock.OpenCC.return_value = converter

            candidate = zh_variant_lexicon.generate_opencc_candidate(
                "人工智能系統依賴网络。",
                config="t2tw",
            )

        opencc_mock.OpenCC.assert_called_once_with("t2tw")
        converter.convert.assert_called_once_with("人工智能系統依賴网络。")
        self.assertEqual(candidate, "人工智慧系統依賴網路。")

    def test_generate_opencc_candidate_returns_original_when_opencc_unavailable(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", None, create=True):
            candidate = zh_variant_lexicon.generate_opencc_candidate(
                "人工智能系統依賴网络。",
                config="t2tw",
            )

        self.assertEqual(candidate, "人工智能系統依賴网络。")

    def test_normalize_with_opencc_returns_identity_when_opencc_unavailable(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", None, create=True):
            result = zh_variant_lexicon.normalize_with_opencc(
                "人工智能系統依賴网络。",
                config="s2twp",
            )

        self.assertEqual(
            result,
            {
                "original_text": "人工智能系統依賴网络。",
                "candidate_text": "人工智能系統依賴网络。",
                "config": "s2twp",
                "opencc_available": False,
                "changed": False,
                "variant_changes": [],
                "regional_auto_fixes": [],
                "regional_flagged_variants": [],
                "normalized_text": "人工智能系統依賴网络。",
            },
        )

    def test_normalize_with_opencc_returns_structured_result_shell(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            converter = mock.Mock()
            converter.convert.return_value = "人工智慧系統依賴網路。"
            opencc_mock.OpenCC.return_value = converter

            result = zh_variant_lexicon.normalize_with_opencc(
                "人工智能系統依賴网络。",
            )

        self.assertEqual(
            result,
            {
                "original_text": "人工智能系統依賴网络。",
                "candidate_text": "人工智慧系統依賴網路。",
                "config": "s2twp",
                "opencc_available": True,
                "changed": True,
                "variant_changes": [
                    {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                    {"source_text": "网络", "replacement_text": "網路", "confidence": "high", "start": 8, "end": 10},
                ],
                "regional_auto_fixes": [
                    {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                    {"source_text": "网络", "replacement_text": "網路", "confidence": "high", "start": 8, "end": 10},
                ],
                "regional_flagged_variants": [],
                "normalized_text": "人工智慧系統依賴網路。",
            },
        )


class RegionalLexiconDiffTests(unittest.TestCase):
    def test_extract_variant_changes_returns_structured_phrase_replacements(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "人工智能系統依賴网络和芯片。",
            "人工智慧系統依賴網路和晶片。",
        )

        self.assertEqual(
            [item["source_text"] for item in result],
            ["人工智能", "网络", "芯片"],
        )
        self.assertEqual(
            [item["replacement_text"] for item in result],
            ["人工智慧", "網路", "晶片"],
        )
        self.assertTrue(all(item["confidence"] == "high" for item in result))
        self.assertEqual(result[0]["start"], 0)
        self.assertEqual(result[0]["end"], 4)

    def test_extract_variant_changes_groups_nearby_phrase_replacements(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "人工智能系統依賴网络和芯片。",
            "人工智慧系統依賴網路和晶片。",
        )

        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["source_text"], "网络")
        self.assertEqual(result[1]["replacement_text"], "網路")

    def test_extract_variant_changes_keeps_adjacent_separator_outside_phrase_spans(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "软件和硬件",
            "軟體和硬體",
        )

        self.assertEqual(
            [item["source_text"] for item in result],
            ["软件", "硬件"],
        )
        self.assertEqual(
            [item["replacement_text"] for item in result],
            ["軟體", "硬體"],
        )
        self.assertTrue(all("和" not in item["source_text"] for item in result))

    def test_extract_variant_changes_keeps_support_online_music_to_clean_local_replacements_only(self):
        result = zh_variant_lexicon.extract_variant_changes("支持在线音乐", "支援線上音樂")

        self.assertEqual(
            [item["source_text"] for item in result],
            ["支持在线", "音乐"],
        )
        self.assertEqual(
            [item["replacement_text"] for item in result],
            ["支援線上", "音樂"],
        )
        self.assertEqual([item["confidence"] for item in result], ["low", "high"])

    def test_extract_variant_changes_ignores_about_network_rewrite(self):
        result = zh_variant_lexicon.extract_variant_changes("关于网络", "關於網路")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], "low")
        self.assertEqual(result[0]["source_text"], "关于网络")
        self.assertEqual(result[0]["replacement_text"], "關於網路")

    def test_extract_variant_changes_returns_empty_list_for_noop_conversion(self):
        result = zh_variant_lexicon.extract_variant_changes("人工智慧系統", "人工智慧系統")

        self.assertEqual(result, [])

    def test_extract_variant_changes_ignores_ambiguous_single_character_changes(self):
        result = zh_variant_lexicon.extract_variant_changes("后", "後")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], "low")
        self.assertEqual(result[0]["source_text"], "后")
        self.assertEqual(result[0]["replacement_text"], "後")

    def test_apply_high_confidence_variant_fixes_only_rewrites_high_confidence_spans(self):
        changes = [
            {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
            {"source_text": "后", "replacement_text": "後", "confidence": "low", "start": 4, "end": 5},
        ]

        result = zh_variant_lexicon.apply_high_confidence_variant_fixes("人工智能后", changes)

        self.assertEqual(result["normalized_text"], "人工智慧后")
        self.assertEqual(len(result["regional_auto_fixes"]), 1)
        self.assertEqual(len(result["regional_flagged_variants"]), 1)

    def test_extract_variant_changes_marks_punctuation_only_changes_low(self):
        result = zh_variant_lexicon.extract_variant_changes("，", "。")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], "low")
        self.assertEqual(result[0]["source_text"], "，")
        self.assertEqual(result[0]["replacement_text"], "。")

    def test_extract_variant_changes_ignores_broad_multi_token_rewrite(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "该软件可用于云计算",
            "該軟體可用於雲端運算",
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(all(item["confidence"] == "low" for item in result))
        self.assertEqual(
            [item["source_text"] for item in result],
            ["该软件", "可用于云计算"],
        )
        self.assertEqual(
            [item["replacement_text"] for item in result],
            ["該軟體", "可用於雲端運算"],
        )

    def test_extract_variant_changes_ignores_broad_domain_rewrite(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "移动互联网",
            "行動網際網路",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], "low")
        self.assertEqual(result[0]["source_text"], "移动互联网")
        self.assertEqual(result[0]["replacement_text"], "行動網際網路")

    def test_extract_variant_changes_ignores_connector_bounded_rewrite(self):
        result = zh_variant_lexicon.extract_variant_changes(
            "后端和前端",
            "後端和前端",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], "low")
        self.assertEqual(result[0]["source_text"], "后端和前端")
        self.assertEqual(result[0]["replacement_text"], "後端和前端")

    def test_normalize_with_opencc_exposes_variant_change_report(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", None), mock.patch.object(
            zh_variant_lexicon, "generate_opencc_candidate", return_value="人工智慧系統"
        ), mock.patch.object(
            zh_variant_lexicon,
            "extract_variant_changes",
            return_value=[
            {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
            ],
        ) as changes_mock, mock.patch.object(
            zh_variant_lexicon,
            "apply_high_confidence_variant_fixes",
            return_value={
                "normalized_text": "人工智慧系統",
                "regional_auto_fixes": [
                    {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                ],
                "regional_flagged_variants": [],
            },
        ) as apply_mock:
            result = zh_variant_lexicon.normalize_with_opencc("人工智能系統")

        changes_mock.assert_called_once_with("人工智能系統", "人工智慧系統")
        apply_mock.assert_called_once()
        self.assertEqual(
            result,
            {
                "original_text": "人工智能系統",
                "candidate_text": "人工智慧系統",
                "config": "s2twp",
                "opencc_available": False,
                "changed": True,
                "variant_changes": [
                    {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                ],
                "regional_auto_fixes": [
                    {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                ],
                "regional_flagged_variants": [],
                "normalized_text": "人工智慧系統",
            },
        )


if __name__ == "__main__":
    unittest.main()
