import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import chunk_audit  # noqa: E402


class AuditChunkTests(unittest.TestCase):
    def test_flags_empty_translation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("Hello world", encoding="utf-8")
            refined.write_text("", encoding="utf-8")

            result = chunk_audit.audit_chunk(str(source), str(refined))

            self.assertFalse(result["ok"])
            self.assertIn("empty", result["reasons"])

    def test_flags_suspiciously_short_translation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("This is a long enough source paragraph for checking.", encoding="utf-8")
            refined.write_text("短", encoding="utf-8")

            result = chunk_audit.audit_chunk(str(source), str(refined))

            self.assertFalse(result["ok"])
            self.assertIn("too_short", result["reasons"])

    def test_flags_residual_english(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("Hello world this is a paragraph.", encoding="utf-8")
            refined.write_text("Hello world this is still mostly English.", encoding="utf-8")

            result = chunk_audit.audit_chunk(str(source), str(refined))

            self.assertFalse(result["ok"])
            self.assertIn("residual_english", result["reasons"])

    def test_flags_term_mismatch_when_glossary_check_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("A compiler handles arithmetic.", encoding="utf-8")
            refined.write_text("編譯程式處理算術。", encoding="utf-8")

            with unittest.mock.patch.object(
                chunk_audit,
                "check_term_mismatches",
                return_value={"matched_terms": 1, "mismatches": 1, "issues": [{"source_term": "compiler"}]},
            ) as mismatch_mock:
                result = chunk_audit.audit_chunk(
                    str(source),
                    str(refined),
                    glossary_db="terms.sqlite3",
                    glossary_dataset="電子計算機名詞",
                    glossary_domain="computer-science",
                )

            mismatch_mock.assert_called_once_with(
                "terms.sqlite3",
                source_text="A compiler handles arithmetic.",
                translated_text="編譯程式處理算術。",
                dataset="電子計算機名詞",
                domain="computer-science",
                high_confidence_only=True,
            )
            self.assertFalse(result["ok"])
            self.assertIn("term_mismatch", result["reasons"])

    def test_flags_term_mismatch_with_auto_selected_datasets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("A compiler handles arithmetic.", encoding="utf-8")
            refined.write_text("編譯程式處理算術。", encoding="utf-8")

            with unittest.mock.patch.object(
                chunk_audit,
                "auto_select_datasets",
                return_value=["電子計算機名詞"],
            ) as auto_select_mock, unittest.mock.patch.object(
                chunk_audit,
                "check_term_mismatches",
                return_value={"matched_terms": 1, "mismatches": 1, "issues": [{"source_term": "compiler"}]},
            ) as mismatch_mock:
                result = chunk_audit.audit_chunk(
                    str(source),
                    str(refined),
                    glossary_db="terms.sqlite3",
                    glossary_auto_select=True,
                )

            auto_select_mock.assert_called_once_with(
                "terms.sqlite3",
                "A compiler handles arithmetic.",
                dataset_candidates=None,
                domain=None,
                max_datasets=2,
            )
            mismatch_mock.assert_called_once_with(
                "terms.sqlite3",
                source_text="A compiler handles arithmetic.",
                translated_text="編譯程式處理算術。",
                dataset=["電子計算機名詞"],
                domain=None,
                high_confidence_only=True,
            )
            self.assertFalse(result["ok"])

    def test_applies_regional_lexicon_auto_fix_and_reports_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("人工智能系统依赖网络。", encoding="utf-8")
            refined.write_text("人工智能系统依赖网络。", encoding="utf-8")

            with mock.patch.object(
                chunk_audit,
                "normalize_with_opencc",
                return_value={
                    "normalized_text": "人工智慧系統依賴網路。",
                    "regional_auto_fixes": [
                        {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                    ],
                    "regional_flagged_variants": [],
                },
            ) as normalize_mock:
                result = chunk_audit.audit_chunk(
                    str(source),
                    str(refined),
                    regional_lexicon_config="s2twp",
                    regional_lexicon_auto_fix=True,
                    regional_lexicon_report=True,
                )

            normalize_mock.assert_called_once_with("人工智能系统依赖网络。", config="s2twp")
            self.assertTrue(result["ok"])
            self.assertEqual(result["normalized_text"], "人工智慧系統依賴網路。")
            self.assertEqual(len(result["regional_auto_fixes"]), 1)
            self.assertEqual(result["regional_flagged_variants"], [])
            self.assertNotIn("regional_lexicon", result["reasons"])
            with mock.patch.object(
                chunk_audit,
                "normalize_with_opencc",
                return_value={
                    "normalized_text": "人工智慧系統依賴網路。",
                    "regional_auto_fixes": [
                        {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                    ],
                    "regional_flagged_variants": [],
                },
            ):
                report = chunk_audit.audit_temp_dir(
                    temp_dir,
                    regional_lexicon_config="s2twp",
                    regional_lexicon_auto_fix=True,
                    regional_lexicon_report=True,
                )
            self.assertEqual(report["checked"], 1)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["issues"], [])
            self.assertEqual(report["chunks"][0]["normalized_text"], "人工智慧系統依賴網路。")
            self.assertEqual(len(report["chunks"][0]["regional_auto_fixes"]), 1)
            self.assertFalse(report["chunks"][0]["regional_flagged_variants"])
            self.assertTrue(report["chunks"][0]["ok"])

    def test_flags_regional_lexicon_when_flagged_variants_remain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "chunk0001.md"
            refined = Path(temp_dir) / "refined_chunk0001.md"
            source.write_text("支持在线音乐和网络。", encoding="utf-8")
            refined.write_text("支援線上音樂和網路。", encoding="utf-8")

            with mock.patch.object(
                chunk_audit,
                "normalize_with_opencc",
                return_value={
                    "normalized_text": "支援線上音樂和網路。",
                    "regional_auto_fixes": [
                        {"source_text": "音乐", "replacement_text": "音樂", "confidence": "high", "start": 4, "end": 6},
                        {"source_text": "网络", "replacement_text": "網路", "confidence": "high", "start": 7, "end": 9},
                    ],
                    "regional_flagged_variants": [
                        {"source_text": "支持在线", "replacement_text": "支援線上", "confidence": "low", "start": 0, "end": 4},
                    ],
                },
            ):
                result = chunk_audit.audit_chunk(
                    str(source),
                    str(refined),
                    regional_lexicon_config="s2twp",
                    regional_lexicon_auto_fix=True,
                    regional_lexicon_report=True,
                )

            self.assertFalse(result["ok"])
            self.assertIn("regional_lexicon", result["reasons"])
            self.assertEqual(result["normalized_text"], "支援線上音樂和網路。")
            self.assertEqual(len(result["regional_flagged_variants"]), 1)
            with mock.patch.object(
                chunk_audit,
                "normalize_with_opencc",
                return_value={
                    "normalized_text": "支援線上音樂和網路。",
                    "regional_auto_fixes": [
                        {"source_text": "音乐", "replacement_text": "音樂", "confidence": "high", "start": 4, "end": 6},
                        {"source_text": "网络", "replacement_text": "網路", "confidence": "high", "start": 7, "end": 9},
                    ],
                    "regional_flagged_variants": [
                        {"source_text": "支持在线", "replacement_text": "支援線上", "confidence": "low", "start": 0, "end": 4},
                    ],
                },
            ):
                report = chunk_audit.audit_temp_dir(
                    temp_dir,
                    regional_lexicon_config="s2twp",
                    regional_lexicon_auto_fix=True,
                    regional_lexicon_report=True,
                )
            self.assertEqual(report["checked"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["chunks"][0]["normalized_text"], "支援線上音樂和網路。")
            self.assertEqual(len(report["chunks"][0]["regional_flagged_variants"]), 1)
            self.assertIn("regional_lexicon", report["chunks"][0]["reasons"])
            self.assertEqual(report["issues"][0]["normalized_text"], "支援線上音樂和網路。")
            self.assertEqual(len(report["issues"][0]["regional_flagged_variants"]), 1)
            self.assertIn("regional_lexicon", report["issues"][0]["reasons"])


class PromotionTests(unittest.TestCase):
    def test_promotes_clean_refined_chunk_to_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello world", encoding="utf-8")
            (temp_path / "refined_chunk0001.md").write_text("你好，世界", encoding="utf-8")

            report = chunk_audit.audit_temp_dir(temp_dir, promote=True)

            self.assertEqual(report["promoted"], 1)
            self.assertTrue((temp_path / "output_chunk0001.md").exists())
            self.assertEqual(
                (temp_path / "output_chunk0001.md").read_text(encoding="utf-8"),
                "你好，世界",
            )

    def test_promotes_normalized_chunk_to_output_when_regional_auto_fix_is_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("人工智能系统依赖网络。", encoding="utf-8")
            (temp_path / "refined_chunk0001.md").write_text("人工智能系统依赖网络。", encoding="utf-8")

            with mock.patch.object(
                chunk_audit,
                "normalize_with_opencc",
                return_value={
                    "normalized_text": "人工智慧系統依賴網路。",
                    "regional_auto_fixes": [
                        {"source_text": "人工智能", "replacement_text": "人工智慧", "confidence": "high", "start": 0, "end": 4},
                    ],
                    "regional_flagged_variants": [],
                },
            ):
                report = chunk_audit.audit_temp_dir(
                    temp_dir,
                    promote=True,
                    regional_lexicon_auto_fix=True,
                    regional_lexicon_report=True,
                )

            self.assertEqual(report["promoted"], 1)
            self.assertEqual(
                (temp_path / "output_chunk0001.md").read_text(encoding="utf-8"),
                "人工智慧系統依賴網路。",
            )
            self.assertEqual(report["chunks"][0]["normalized_text"], "人工智慧系統依賴網路。")
            self.assertTrue(report["chunks"][0]["promoted"])


if __name__ == "__main__":
    unittest.main()
