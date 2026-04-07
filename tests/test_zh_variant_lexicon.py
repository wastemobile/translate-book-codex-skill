import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import zh_variant_lexicon  # noqa: E402


class OpenCCWrapperTests(unittest.TestCase):
    def test_build_converter_uses_config_name(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            opencc_mock.OpenCC.return_value = mock.Mock()

            converter = zh_variant_lexicon.build_converter("s2twp")

        opencc_mock.OpenCC.assert_called_once_with("s2twp")
        self.assertIsNotNone(converter)

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

    def test_normalize_with_opencc_returns_structured_result_shell(self):
        with mock.patch.object(zh_variant_lexicon, "opencc", create=True) as opencc_mock:
            converter = mock.Mock()
            converter.convert.return_value = "人工智慧系統依賴網路。"
            opencc_mock.OpenCC.return_value = converter

            result = zh_variant_lexicon.normalize_with_opencc(
                "人工智能系統依賴网络。",
                config="t2tw",
            )

        self.assertEqual(
            result,
            {
                "original_text": "人工智能系統依賴网络。",
                "candidate_text": "人工智慧系統依賴網路。",
                "config": "t2tw",
                "opencc_available": True,
                "changed": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
