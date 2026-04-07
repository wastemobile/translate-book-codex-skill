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
    def test_build_repair_prompt_targets_only_mismatched_terms(self):
        prompt = ollama_stage_refine.build_repair_prompt(
            "A compiler handles arithmetic. The assembly line is next.",
            "編譯程式處理算術。",
            {"source_term": "compiler", "expected_target": "編譯器"},
            "Traditional Chinese",
        )

        self.assertIn("Fix only the terminology mismatches", prompt)
        self.assertIn("compiler -> 編譯器", prompt)
        self.assertIn("RELEVANT SOURCE EXCERPTS:", prompt)
        self.assertIn("A compiler handles arithmetic.", prompt)
        self.assertIn("CURRENT TRANSLATION:", prompt)
        self.assertIn("Do not add explanations", prompt)

    def test_sanitize_repair_output_strips_preface_before_translation_anchor(self):
        current = "# 標題\n\n編譯程式處理算術。"
        candidate = "以下為修正版：\n\n# 標題\n\n編譯器處理算術。"

        cleaned = ollama_stage_refine.sanitize_repair_output(candidate, current)

        self.assertEqual(cleaned, "# 標題\n\n編譯器處理算術。")

    def test_sanitize_repair_output_does_not_trim_to_later_paragraph_anchor(self):
        current = "# 標題\n\n第一段。\n\n第二段。"
        candidate = "第二段。\n\n補充說明。"

        cleaned = ollama_stage_refine.sanitize_repair_output(candidate, current)

        self.assertEqual(cleaned, "第二段。\n\n補充說明。")

    def test_build_prompt_includes_glossary_block_when_present(self):
        prompt = ollama_stage_refine.build_prompt(
            "A compiler handles arithmetic.",
            "一個編譯程式處理算術。",
            "Traditional Chinese",
            glossary_block="Terminology references for this chunk:\n- compiler -> 編譯器",
        )

        self.assertIn("Terminology references for this chunk:", prompt)
        self.assertIn("- compiler -> 編譯器", prompt)
        self.assertIn("DRAFT:", prompt)

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

    def test_generate_refinement_uses_glossary_lookup_when_db_configured(self):
        with mock.patch.object(
            ollama_stage_refine,
            "build_glossary_block",
            return_value="Terminology references for this chunk:\n- compiler -> 編譯器",
        ) as glossary_mock, mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            return_value="編譯器",
        ) as generate_mock:
            ollama_stage_refine.generate_refinement(
                "A compiler is here.",
                "一個編譯程式在這裡。",
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

    def test_repair_refinement_uses_mismatch_report_when_present(self):
        with mock.patch.object(
            ollama_stage_refine,
            "check_term_mismatches",
            side_effect=[
                {
                    "matched_terms": 1,
                    "mismatches": 1,
                    "issues": [{"source_term": "compiler", "expected_target": "編譯器"}],
                },
                {
                    "matched_terms": 1,
                    "mismatches": 0,
                    "issues": [],
                },
            ],
        ) as mismatch_mock, mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            return_value="編譯器處理算術。",
        ) as generate_mock:
            result = ollama_stage_refine.repair_terminology_mismatches(
                "A compiler handles arithmetic.",
                "編譯程式處理算術。",
                target_lang="Traditional Chinese",
                glossary_db="terms.sqlite3",
                glossary_dataset="電子計算機名詞",
                glossary_domain="computer-science",
            )

        self.assertEqual(result, "編譯器處理算術。")
        self.assertEqual(mismatch_mock.call_count, 2)
        self.assertEqual(
            mismatch_mock.call_args_list[0],
            mock.call(
                "terms.sqlite3",
                source_text="A compiler handles arithmetic.",
                translated_text="編譯程式處理算術。",
                dataset="電子計算機名詞",
                domain="computer-science",
                high_confidence_only=True,
            ),
        )
        self.assertIn("compiler -> 編譯器", generate_mock.call_args.args[0])

    def test_repair_refinement_processes_issues_one_by_one(self):
        with mock.patch.object(
            ollama_stage_refine,
            "check_term_mismatches",
            side_effect=[
                {
                    "matched_terms": 2,
                    "mismatches": 2,
                    "issues": [
                        {"source_term": "compiler", "expected_target": "編譯器"},
                        {"source_term": "assembly line", "expected_target": "裝配線"},
                    ],
                },
                {
                    "matched_terms": 2,
                    "mismatches": 1,
                    "issues": [{"source_term": "assembly line", "expected_target": "裝配線"}],
                },
                {
                    "matched_terms": 2,
                    "mismatches": 0,
                    "issues": [],
                },
            ],
        ), mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            side_effect=["編譯器處理算術。裝配線在後面。", "編譯器處理算術。裝配線在後面。"],
        ) as generate_mock:
            result = ollama_stage_refine.repair_terminology_mismatches(
                "A compiler handles arithmetic. The assembly line is next.",
                "編譯程式處理算術。組裝線在後面。",
                glossary_db="terms.sqlite3",
                glossary_dataset="電子計算機名詞",
            )

        self.assertEqual(result, "編譯器處理算術。裝配線在後面。")
        self.assertEqual(generate_mock.call_count, 2)

    def test_repair_refinement_rejects_candidate_when_mismatches_do_not_improve(self):
        with mock.patch.object(
            ollama_stage_refine,
            "check_term_mismatches",
            side_effect=[
                {
                    "matched_terms": 1,
                    "mismatches": 1,
                    "issues": [{"source_term": "compiler", "expected_target": "編譯器"}],
                },
                {
                    "matched_terms": 1,
                    "mismatches": 1,
                    "issues": [{"source_term": "compiler", "expected_target": "編譯器"}],
                },
            ],
        ), mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            return_value="前言\n\n# 標題\n\n編譯程式處理算術。",
        ):
            result = ollama_stage_refine.repair_terminology_mismatches(
                "A compiler handles arithmetic.",
                "# 標題\n\n編譯程式處理算術。",
                glossary_db="terms.sqlite3",
                glossary_dataset="電子計算機名詞",
            )

        self.assertEqual(result, "# 標題\n\n編譯程式處理算術。")

    def test_repair_refinement_skips_model_call_when_no_mismatch(self):
        with mock.patch.object(
            ollama_stage_refine,
            "check_term_mismatches",
            return_value={"matched_terms": 1, "mismatches": 0, "issues": []},
        ), mock.patch.object(
            ollama_stage_refine,
            "generate_text",
        ) as generate_mock:
            result = ollama_stage_refine.repair_terminology_mismatches(
                "A compiler handles arithmetic.",
                "編譯器處理算術。",
                glossary_db="terms.sqlite3",
            )

        self.assertEqual(result, "編譯器處理算術。")
        generate_mock.assert_not_called()

    def test_refine_one_runs_repair_after_refinement_when_enabled(self):
        item = {"source": "source.md", "draft": "draft.md", "refined": "refined.md"}
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            item = {
                "source": str(temp_path / "chunk0001.md"),
                "draft": str(temp_path / "draft_chunk0001.md"),
                "refined": str(temp_path / "refined_chunk0001.md"),
            }
            Path(item["source"]).write_text("A compiler handles arithmetic.", encoding="utf-8")
            Path(item["draft"]).write_text("編譯程式處理算術。", encoding="utf-8")

            with mock.patch.object(
                ollama_stage_refine,
                "generate_refinement",
                return_value="編譯程式處理算術。",
            ) as refine_mock, mock.patch.object(
                ollama_stage_refine,
                "repair_terminology_mismatches",
                return_value="編譯器處理算術。",
            ) as repair_mock:
                ok, output = ollama_stage_refine.refine_one(
                    item,
                    "Traditional Chinese",
                    ollama_stage_refine.DEFAULT_MODEL,
                    "omlx",
                    "http://127.0.0.1:8000/v1",
                    None,
                    1,
                    glossary_db="terms.sqlite3",
                    glossary_dataset="電子計算機名詞",
                    repair_glossary_mismatches=True,
                )

            self.assertTrue(ok)
            self.assertEqual(output, item["refined"])
            refine_mock.assert_called_once()
            repair_mock.assert_called_once()
            self.assertEqual(Path(item["refined"]).read_text(encoding="utf-8"), "編譯器處理算術。")

    def test_generate_refinement_auto_selects_datasets_when_enabled(self):
        with mock.patch.object(
            ollama_stage_refine,
            "auto_select_datasets",
            return_value=["電子計算機名詞"],
        ) as auto_select_mock, mock.patch.object(
            ollama_stage_refine,
            "build_glossary_block",
            return_value="Terminology references for this chunk:\n- compiler -> 編譯器",
        ) as glossary_mock, mock.patch.object(
            ollama_stage_refine,
            "generate_text",
            return_value="編譯器",
        ):
            ollama_stage_refine.generate_refinement(
                "A compiler is here.",
                "一個編譯程式在這裡。",
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
            dataset=["電子計算機名詞"],
            domain=None,
            high_confidence_only=True,
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
