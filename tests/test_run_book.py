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
        with mock.patch.object(run_book.preflight, "run_preflight", return_value={"status": "ok"}) as preflight_mock, mock.patch.object(
            run_book, "run_step"
        ) as run_step_mock:
            report = run_book.run_pipeline(
                input_file="novel.epub",
                target_lang="zh-TW",
                output_formats="epub",
            )

        self.assertEqual(report["status"], "ok")
        preflight_mock.assert_called_once_with(
            input_file="novel.epub",
            stage2_model="gemma-4-e4b-it-8bit",
            stage3_model="gemma-4-26b-a4b-it-4bit",
            api_base="http://127.0.0.1:8000/v1",
            api_key=None,
        )
        self.assertEqual(run_step_mock.call_count, 5)
        draft_command = run_step_mock.call_args_list[1].args[1]
        refine_command = run_step_mock.call_args_list[2].args[1]
        audit_command = run_step_mock.call_args_list[3].args[1]
        merge_command = run_step_mock.call_args_list[4].args[1]
        self.assertIn("gemma-4-e4b-it-8bit", draft_command)
        self.assertIn("gemma-4-26b-a4b-it-4bit", refine_command)
        self.assertIn("--promote", audit_command)
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


if __name__ == "__main__":
    unittest.main()
