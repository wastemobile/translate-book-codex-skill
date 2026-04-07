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
    def test_build_prompt_includes_glossary_block_when_present(self):
        prompt = ollama_stage_translate.build_prompt(
            "A compiler handles arithmetic.",
            "Traditional Chinese",
            glossary_block="Terminology references for this chunk:\n- compiler -> 編譯器",
        )

        self.assertIn("Terminology references for this chunk:", prompt)
        self.assertIn("- compiler -> 編譯器", prompt)
        self.assertIn("SOURCE:", prompt)

    def test_generate_translation_uses_omlx_defaults(self):
        with mock.patch.object(
            ollama_stage_translate,
            "generate_text",
            return_value="# 你好\n\n世界",
        ) as generate_mock:
            result = ollama_stage_translate.generate_translation("# Hello\n\nWorld")

        self.assertEqual(result, "# 你好\n\n世界")
        generate_mock.assert_called_once_with(
            mock.ANY,
            model="aya-expanse-8b-4bit-mlx",
            provider="omlx",
            api_base="http://127.0.0.1:8000/v1",
            api_key=None,
            temperature=0.2,
        )

    def test_generate_translation_uses_glossary_lookup_when_db_configured(self):
        with mock.patch.object(
            ollama_stage_translate,
            "build_glossary_block",
            return_value="Terminology references for this chunk:\n- compiler -> 編譯器",
        ) as glossary_mock, mock.patch.object(
            ollama_stage_translate,
            "generate_text",
            return_value="編譯器",
        ) as generate_mock:
            ollama_stage_translate.generate_translation(
                "A compiler is here.",
                glossary_db="terms.sqlite3",
                glossary_dataset="電子計算機名詞",
                glossary_domain="computer-science",
            )

        glossary_mock.assert_called_once_with(
            "terms.sqlite3",
            "A compiler is here.",
            dataset="電子計算機名詞",
            domain="computer-science",
            high_confidence_only=True,
        )
        self.assertIn(
            "Terminology references for this chunk:",
            generate_mock.call_args.args[0],
        )

    def test_generate_translation_auto_selects_datasets_when_enabled(self):
        with mock.patch.object(
            ollama_stage_translate,
            "auto_select_datasets",
            return_value=["電子計算機名詞", "電機工程名詞"],
        ) as auto_select_mock, mock.patch.object(
            ollama_stage_translate,
            "build_glossary_block",
            return_value="Terminology references for this chunk:\n- compiler -> 編譯器",
        ) as glossary_mock, mock.patch.object(
            ollama_stage_translate,
            "generate_text",
            return_value="編譯器",
        ):
            ollama_stage_translate.generate_translation(
                "A compiler is here.",
                glossary_db="terms.sqlite3",
                glossary_auto_select=True,
            )

        auto_select_mock.assert_called_once_with(
            "terms.sqlite3",
            "A compiler is here.",
            dataset_candidates=None,
            domain=None,
            max_datasets=2,
        )
        glossary_mock.assert_called_once_with(
            "terms.sqlite3",
            "A compiler is here.",
            dataset=["電子計算機名詞", "電機工程名詞"],
            domain=None,
            high_confidence_only=True,
        )

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
