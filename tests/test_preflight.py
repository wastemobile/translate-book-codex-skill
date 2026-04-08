import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import preflight  # noqa: E402


class PreflightTests(unittest.TestCase):
    def test_reports_missing_optional_and_required_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            book_path = Path(temp_dir) / "book.epub"
            book_path.write_text("stub", encoding="utf-8")

            with mock.patch.object(preflight, "find_executable") as find_executable_mock, mock.patch.object(
                preflight, "find_python_module"
            ) as find_module_mock, mock.patch.object(
                preflight, "fetch_model_ids"
            ) as fetch_model_ids_mock:
                find_executable_mock.side_effect = lambda name: None if name == "pandoc" else f"/usr/bin/{name}"
                find_module_mock.side_effect = lambda name: name != "opencc"
                fetch_model_ids_mock.return_value = ["gemma-4-e4b-it-8bit", "gemma-4-26b-a4b-it-4bit"]

                report = preflight.run_preflight(
                    input_file=str(book_path),
                    stage2_model="gemma-4-e4b-it-8bit",
                    stage3_model="gemma-4-26b-a4b-it-4bit",
                    api_base="http://127.0.0.1:8000/v1",
                    api_key="kr4fi8",
                )

            self.assertEqual(report["status"], "fail")
            self.assertGreaterEqual(report["summary"]["fail"], 1)
            self.assertGreaterEqual(report["summary"]["warn"], 1)
            checks = {item["name"]: item for item in report["checks"]}
            self.assertEqual(checks["pandoc"]["status"], "fail")
            self.assertEqual(checks["opencc"]["status"], "warn")
            self.assertEqual(checks["model_api"]["status"], "ok")
            self.assertEqual(checks["stage3_model"]["status"], "ok")

    def test_fetch_model_ids_reads_openai_style_model_list(self):
        response = {
            "data": [
                {"id": "gemma-4-e4b-it-8bit"},
                {"id": "gemma-4-26b-a4b-it-4bit"},
            ]
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(response).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False

        with mock.patch.object(preflight.request, "urlopen", return_value=mock_response) as urlopen_mock:
            model_ids = preflight.fetch_model_ids("http://127.0.0.1:8000/v1", api_key="kr4fi8")

        self.assertEqual(model_ids, ["gemma-4-e4b-it-8bit", "gemma-4-26b-a4b-it-4bit"])
        headers = dict(urlopen_mock.call_args.args[0].header_items())
        self.assertEqual(headers["Authorization"], "Bearer kr4fi8")


if __name__ == "__main__":
    unittest.main()
