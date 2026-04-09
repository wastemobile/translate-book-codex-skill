import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_book  # noqa: E402


class RunBookTests(unittest.TestCase):
    def test_uses_default_models_and_formats_when_not_overridden(self):
        with mock.patch.object(run_book, "resolve_python_executable", return_value="/shared/python") as python_mock, mock.patch.object(
            run_book.preflight, "run_preflight", return_value={"status": "ok"}
        ) as preflight_mock, mock.patch.object(run_book, "run_step") as run_step_mock:
            report = run_book.run_pipeline(
                input_file="novel.epub",
                target_lang="zh-TW",
                output_formats="epub",
            )

        self.assertEqual(report["status"], "ok")
        python_mock.assert_called_once_with()
        preflight_mock.assert_called_once_with(
            input_file="novel.epub",
            stage2_model="gemma-4-e4b-it-8bit",
            stage3_model="gemma-4-26b-a4b-it-4bit",
            api_base="http://127.0.0.1:8000/v1",
            api_key=None,
            python_executable="/shared/python",
            glossary_db=run_book.DEFAULT_GLOSSARY_DB,
            require_opencc=True,
        )
        self.assertEqual(run_step_mock.call_count, 5)
        convert_command = run_step_mock.call_args_list[0].args[1]
        draft_command = run_step_mock.call_args_list[1].args[1]
        refine_command = run_step_mock.call_args_list[2].args[1]
        audit_command = run_step_mock.call_args_list[3].args[1]
        merge_command = run_step_mock.call_args_list[4].args[1]
        self.assertEqual(convert_command[0], "/shared/python")
        self.assertIn("gemma-4-e4b-it-8bit", draft_command)
        self.assertIn("gemma-4-26b-a4b-it-4bit", refine_command)
        self.assertIn(run_book.DEFAULT_GLOSSARY_DB, draft_command)
        self.assertIn("--glossary-auto-select", draft_command)
        self.assertIn("--repair-glossary-mismatches", refine_command)
        self.assertIn("--promote", audit_command)
        self.assertIn("--regional-lexicon-auto-fix", audit_command)
        self.assertIn("epub", merge_command)

    def test_stops_immediately_when_preflight_fails(self):
        with mock.patch.object(
            run_book.preflight,
            "run_preflight",
            return_value={"status": "fail", "checks": [{"name": "pandoc", "status": "fail"}]},
        ), mock.patch.object(run_book, "run_step") as run_step_mock:
            report = run_book.run_pipeline(input_file="novel.epub")

        self.assertEqual(report["status"], "fail")
        self.assertIn("preflight", report)
        run_step_mock.assert_not_called()

    def test_returns_structured_failure_when_a_stage_fails(self):
        with mock.patch.object(run_book, "resolve_python_executable", return_value="/shared/python"), mock.patch.object(
            run_book.preflight,
            "run_preflight",
            return_value={"status": "ok"},
        ), mock.patch.object(
            run_book,
            "run_step",
            side_effect=[
                {"name": "convert", "status": "ok", "command": ["/shared/python", "convert.py"]},
                {
                    "name": "draft",
                    "status": "fail",
                    "command": ["/shared/python", "ollama_stage_translate.py"],
                    "error": "model overloaded",
                },
            ],
        ) as run_step_mock:
            report = run_book.run_pipeline(input_file="novel.epub")

        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["temp_dir"], "novel_temp")
        self.assertEqual(
            report["steps"],
            [
                {"name": "convert", "status": "ok", "command": ["/shared/python", "convert.py"]},
                {
                    "name": "draft",
                    "status": "fail",
                    "command": ["/shared/python", "ollama_stage_translate.py"],
                    "error": "model overloaded",
                },
            ],
        )
        self.assertEqual(run_step_mock.call_count, 2)

    def test_uses_local_llm_api_key_from_environment_when_not_explicitly_passed(self):
        with mock.patch.dict("os.environ", {"LOCAL_LLM_API_KEY": "env-key"}, clear=False), mock.patch.object(
            run_book, "resolve_python_executable", return_value="/shared/python"
        ), mock.patch.object(
            run_book.preflight, "run_preflight", return_value={"status": "ok"}
        ) as preflight_mock, mock.patch.object(run_book, "run_step") as run_step_mock:
            run_book.run_pipeline(input_file="novel.epub", target_lang="zh-TW")

        self.assertEqual(preflight_mock.call_args.kwargs["api_key"], "env-key")
        draft_command = run_step_mock.call_args_list[1].args[1]
        self.assertIn("--api-key", draft_command)
        self.assertIn("env-key", draft_command)


if __name__ == "__main__":
    unittest.main()
