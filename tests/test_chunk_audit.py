import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
