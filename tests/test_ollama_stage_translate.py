import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ollama_stage_translate  # noqa: E402


class DiscoverPendingChunksTests(unittest.TestCase):
    def test_discovers_only_chunks_without_draft_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("one", encoding="utf-8")
            (temp_path / "chunk0002.md").write_text("two", encoding="utf-8")
            (temp_path / "draft_chunk0001.md").write_text("done", encoding="utf-8")

            pending = ollama_stage_translate.discover_pending_chunks(temp_dir)

            self.assertEqual([Path(p["source"]).name for p in pending], ["chunk0002.md"])
            self.assertEqual([Path(p["draft"]).name for p in pending], ["draft_chunk0002.md"])


class DraftTranslationPipelineTests(unittest.TestCase):
    def test_process_temp_dir_writes_draft_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("# Hello\n\nWorld", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_translate,
                "generate_translation",
                return_value="# 你好\n\n世界",
            ) as generate_mock:
                report = ollama_stage_translate.process_temp_dir(temp_dir, parallelism=1)

            self.assertEqual(report["completed"], 1)
            self.assertTrue((temp_path / "draft_chunk0001.md").exists())
            self.assertEqual(
                (temp_path / "draft_chunk0001.md").read_text(encoding="utf-8"),
                "# 你好\n\n世界",
            )
            generate_mock.assert_called_once()

    def test_process_temp_dir_retries_once_before_succeeding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_translate,
                "generate_translation",
                side_effect=[RuntimeError("boom"), "哈囉"],
            ) as generate_mock:
                report = ollama_stage_translate.process_temp_dir(
                    temp_dir, parallelism=1, max_attempts=2
                )

            self.assertEqual(report["completed"], 1)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(generate_mock.call_count, 2)
            self.assertEqual(
                (temp_path / "draft_chunk0001.md").read_text(encoding="utf-8"),
                "哈囉",
            )

    def test_process_temp_dir_leaves_failed_chunk_without_draft_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_translate,
                "generate_translation",
                side_effect=RuntimeError("boom"),
            ):
                report = ollama_stage_translate.process_temp_dir(
                    temp_dir, parallelism=1, max_attempts=2
                )

            self.assertEqual(report["completed"], 0)
            self.assertEqual(report["failed"], 1)
            self.assertFalse((temp_path / "draft_chunk0001.md").exists())


if __name__ == "__main__":
    unittest.main()
