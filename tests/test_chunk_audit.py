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
