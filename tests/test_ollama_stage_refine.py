import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ollama_stage_refine  # noqa: E402


class DiscoverPendingRefinementsTests(unittest.TestCase):
    def test_discovers_source_and_draft_pairs_missing_refined_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("one", encoding="utf-8")
            (temp_path / "draft_chunk0001.md").write_text("一", encoding="utf-8")
            (temp_path / "chunk0002.md").write_text("two", encoding="utf-8")
            (temp_path / "draft_chunk0002.md").write_text("二", encoding="utf-8")
            (temp_path / "refined_chunk0002.md").write_text("二", encoding="utf-8")

            pending = ollama_stage_refine.discover_pending_refinements(temp_dir)

            self.assertEqual(len(pending), 1)
            self.assertEqual(Path(pending[0]["source"]).name, "chunk0001.md")
            self.assertEqual(Path(pending[0]["draft"]).name, "draft_chunk0001.md")
            self.assertEqual(Path(pending[0]["refined"]).name, "refined_chunk0001.md")


class RefinePipelineTests(unittest.TestCase):
    def test_generate_refinement_uses_omlx_defaults(self):
        with mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            return_value="你好，世界",
        ) as refine_mock:
            result = ollama_stage_refine.generate_refinement("Hello world", "你好 世界")

        self.assertEqual(result, "你好，世界")
        refine_mock.assert_called_once_with(
            mock.ANY,
            model="gemma-4-26b-a4b-it-mxfp4",
            provider="omlx",
            api_base="http://127.0.0.1:8000/v1",
            api_key=None,
            temperature=0.1,
        )

    def test_process_temp_dir_writes_refined_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello world", encoding="utf-8")
            (temp_path / "draft_chunk0001.md").write_text("你好 世界", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_refine,
                "generate_refinement",
                return_value="你好，世界",
            ) as refine_mock:
                report = ollama_stage_refine.process_temp_dir(temp_dir, parallelism=1)

            self.assertEqual(report["completed"], 1)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(
                (temp_path / "refined_chunk0001.md").read_text(encoding="utf-8"),
                "你好，世界",
            )
            refine_mock.assert_called_once()

    def test_process_temp_dir_rejects_empty_refinement_and_preserves_no_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello world", encoding="utf-8")
            (temp_path / "draft_chunk0001.md").write_text("你好 世界", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_refine,
                "generate_refinement",
                return_value="   ",
            ):
                report = ollama_stage_refine.process_temp_dir(
                    temp_dir, parallelism=1, max_attempts=1
                )

            self.assertEqual(report["completed"], 0)
            self.assertEqual(report["failed"], 1)
            self.assertFalse((temp_path / "refined_chunk0001.md").exists())

    def test_process_temp_dir_retries_once_before_succeeding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "chunk0001.md").write_text("Hello world", encoding="utf-8")
            (temp_path / "draft_chunk0001.md").write_text("你好 世界", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_refine,
                "generate_refinement",
                side_effect=[RuntimeError("boom"), "你好，世界"],
            ) as refine_mock:
                report = ollama_stage_refine.process_temp_dir(
                    temp_dir, parallelism=1, max_attempts=2
                )

            self.assertEqual(report["completed"], 1)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(refine_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
