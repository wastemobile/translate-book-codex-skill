import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import merge_and_build  # noqa: E402


class OutputFormatSelectionTests(unittest.TestCase):
    def test_defaults_to_original_input_extension(self):
        config = {"input_file": "/tmp/book.epub"}

        formats = merge_and_build.resolve_output_formats(config, None)

        self.assertEqual(formats, [".epub"])

    def test_defaults_to_pdf_when_source_is_pdf(self):
        config = {"input_file": "/tmp/book.pdf"}

        formats = merge_and_build.resolve_output_formats(config, None)

        self.assertEqual(formats, [".pdf"])

    def test_accepts_multiple_requested_formats(self):
        config = {"input_file": "/tmp/book.epub"}

        formats = merge_and_build.resolve_output_formats(config, "epub,pdf,docx")

        self.assertEqual(formats, [".epub", ".pdf", ".docx"])


class GenerateFormatTests(unittest.TestCase):
    def _write_file(self, path, content="data"):
        Path(path).write_text(content, encoding="utf-8")

    def _set_mtime(self, path, timestamp):
        os.utime(path, (timestamp, timestamp))

    def test_skips_when_output_is_up_to_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = os.path.join(temp_dir, "book_doc.html")
            output_file = os.path.join(temp_dir, "book.epub")
            self._write_file(html_file, "<html></html>")
            self._write_file(output_file, "epub")
            self._set_mtime(html_file, 100)
            self._set_mtime(output_file, 200)

            with mock.patch.object(merge_and_build.subprocess, "run") as run_mock:
                result = merge_and_build.generate_format(
                    html_file, temp_dir, ".epub", "zh-CN"
                )

            self.assertEqual(result, output_file)
            run_mock.assert_not_called()

    def test_rebuilds_when_image_assets_are_newer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = os.path.join(temp_dir, "book_doc.html")
            output_file = os.path.join(temp_dir, "book.epub")
            images_dir = os.path.join(temp_dir, "images")
            image_file = os.path.join(images_dir, "cover.jpg")

            os.makedirs(images_dir, exist_ok=True)
            self._write_file(html_file, "<html></html>")
            self._write_file(output_file, "epub")
            self._write_file(image_file, "image")

            self._set_mtime(html_file, 100)
            self._set_mtime(output_file, 200)
            self._set_mtime(image_file, 300)

            with mock.patch.object(
                merge_and_build.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="", stderr=""),
            ) as run_mock:
                result = merge_and_build.generate_format(
                    html_file, temp_dir, ".epub", "zh-CN"
                )

            self.assertEqual(result, output_file)
            run_mock.assert_called_once()
            cmd = run_mock.call_args.args[0]
            self.assertEqual(cmd[0], "python3")
            self.assertEqual(cmd[2], html_file)
            self.assertEqual(cmd[4], output_file)

    @unittest.skipUnless(
        "cover" in inspect.signature(merge_and_build.generate_format).parameters,
        "cover support not merged yet",
    )
    def test_rebuilds_epub_when_cover_is_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_file = os.path.join(temp_dir, "book_doc.html")
            output_file = os.path.join(temp_dir, "book.epub")
            cover_file = os.path.join(temp_dir, "cover.jpg")

            self._write_file(html_file, "<html></html>")
            self._write_file(output_file, "epub")
            self._write_file(cover_file, "image")

            self._set_mtime(html_file, 100)
            self._set_mtime(output_file, 200)
            self._set_mtime(cover_file, 300)

            with mock.patch.object(
                merge_and_build.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="", stderr=""),
            ) as run_mock:
                result = merge_and_build.generate_format(
                    html_file, temp_dir, ".epub", "zh-CN", cover=cover_file
                )

            self.assertEqual(result, output_file)
            run_mock.assert_called_once()
            cmd = run_mock.call_args.args[0]
            self.assertIn("--cover", cmd)
            self.assertIn(cover_file, cmd)


class CleanupIntermediateFilesTests(unittest.TestCase):
    def _touch(self, path, content="x"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @unittest.skipUnless(
        hasattr(merge_and_build, "extract_cover_from_epub"),
        "cover extraction support not merged yet",
    )
    def test_cleanup_removes_cover_extract_directory_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cover_extract = temp_path / "cover_extract"
            self._touch(cover_extract / "OPS" / "images" / "cover.jpg", "image")
            self._touch(temp_path / "chunk0001.md", "chunk")
            self._touch(temp_path / "output_chunk0001.md", "translated")
            self._touch(temp_path / "input.html", "<html></html>")

            merge_and_build.cleanup_intermediate_files(temp_dir)

            self.assertFalse((temp_path / "chunk0001.md").exists())
            self.assertFalse((temp_path / "output_chunk0001.md").exists())
            self.assertFalse((temp_path / "input.html").exists())
            self.assertFalse(cover_extract.exists())


class MissingCoverPathTests(unittest.TestCase):
    @unittest.skipUnless(
        "cover" in inspect.signature(merge_and_build.generate_format).parameters,
        "cover support not merged yet",
    )
    def test_main_rejects_missing_cover_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_cover = os.path.join(temp_dir, "missing-cover.jpg")

            with mock.patch.object(
                merge_and_build, "load_config", return_value={}
            ), mock.patch.object(
                merge_and_build, "get_lang_config", return_value={"lang_attr": "zh-CN"}
            ), mock.patch.object(
                merge_and_build, "merge_markdown_files", return_value=True
            ), mock.patch.object(
                merge_and_build, "convert_md_to_html", return_value=True
            ), mock.patch.object(
                merge_and_build, "add_toc", return_value=True
            ), mock.patch.object(
                merge_and_build, "generate_formats"
            ) as generate_formats_mock, mock.patch.object(
                sys, "argv", ["merge_and_build.py", "--temp-dir", temp_dir, "--cover", missing_cover]
            ):
                with self.assertRaises(SystemExit) as exc:
                    merge_and_build.main()

            self.assertNotEqual(exc.exception.code, 0)
            generate_formats_mock.assert_not_called()


class MainFormatSelectionTests(unittest.TestCase):
    def test_main_uses_original_input_format_when_formats_not_provided(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                merge_and_build, "load_config", return_value={"input_file": "/tmp/source.epub"}
            ), mock.patch.object(
                merge_and_build, "get_lang_config", return_value={"lang_attr": "zh-CN"}
            ), mock.patch.object(
                merge_and_build, "merge_markdown_files", return_value=True
            ), mock.patch.object(
                merge_and_build, "convert_md_to_html", return_value=True
            ), mock.patch.object(
                merge_and_build, "add_toc", return_value=True
            ), mock.patch.object(
                merge_and_build, "generate_formats", return_value=True
            ) as generate_formats_mock, mock.patch.object(
                sys, "argv", ["merge_and_build.py", "--temp-dir", temp_dir]
            ):
                merge_and_build.main()

            self.assertEqual(generate_formats_mock.call_args.args[2], [".epub"])

    def test_main_passes_requested_formats_to_generator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                merge_and_build, "load_config", return_value={"input_file": "/tmp/source.epub"}
            ), mock.patch.object(
                merge_and_build, "get_lang_config", return_value={"lang_attr": "zh-CN"}
            ), mock.patch.object(
                merge_and_build, "merge_markdown_files", return_value=True
            ), mock.patch.object(
                merge_and_build, "convert_md_to_html", return_value=True
            ), mock.patch.object(
                merge_and_build, "add_toc", return_value=True
            ), mock.patch.object(
                merge_and_build, "generate_formats", return_value=True
            ) as generate_formats_mock, mock.patch.object(
                sys, "argv", ["merge_and_build.py", "--temp-dir", temp_dir, "--formats", "epub,pdf"]
            ):
                merge_and_build.main()

            self.assertEqual(generate_formats_mock.call_args.args[2], [".epub", ".pdf"])


if __name__ == "__main__":
    unittest.main()
