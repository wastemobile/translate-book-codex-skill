import io
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import naer_terms  # noqa: E402


ODS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body>
    <office:spreadsheet>
      <table:table table:name="電子計算機名詞">
        <table:table-row>
          <table:table-cell office:value-type="string"><text:p>英文名稱</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p>中文名稱</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p>備註</text:p></table:table-cell>
        </table:table-row>
        <table:table-row>
          <table:table-cell office:value-type="string"><text:p>compiler</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p>編譯器</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p>software</text:p></table:table-cell>
        </table:table-row>
        <table:table-row>
          <table:table-cell office:value-type="string"><text:p>floating-point</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p>浮點</text:p></table:table-cell>
          <table:table-cell office:value-type="string"><text:p></text:p></table:table-cell>
        </table:table-row>
      </table:table>
    </office:spreadsheet>
  </office:body>
</office:document-content>
"""


class OdsHelpersTests(unittest.TestCase):
    def test_extracts_first_ods_from_zip_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "naer.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("電子計算機名詞.ods", b"fake-ods")

            extracted = naer_terms.extract_first_ods(zip_path, temp_path)

            self.assertEqual(extracted.name, "電子計算機名詞.ods")
            self.assertEqual(extracted.read_bytes(), b"fake-ods")

    def test_parse_ods_table_extracts_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ods_path = Path(temp_dir) / "sample.ods"
            with zipfile.ZipFile(ods_path, "w") as archive:
                archive.writestr("content.xml", ODS_CONTENT)

            rows = naer_terms.parse_ods_rows(ods_path)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["source_term"], "compiler")
            self.assertEqual(rows[0]["target_term"], "編譯器")
            self.assertEqual(rows[0]["note"], "software")
            self.assertEqual(rows[0]["sheet_name"], "電子計算機名詞")


class ImportAndQueryTests(unittest.TestCase):
    def _create_sample_ods(self, temp_path):
        ods_path = temp_path / "sample.ods"
        with zipfile.ZipFile(ods_path, "w") as archive:
            archive.writestr("content.xml", ODS_CONTENT)
        return ods_path

    def test_import_ods_to_sqlite_and_query_hits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ods_path = self._create_sample_ods(temp_path)
            db_path = temp_path / "terms.sqlite3"
            naer_terms.import_ods_to_sqlite(
                ods_path,
                db_path,
                dataset="電子計算機名詞",
                domain="computer-science",
            )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "A compiler handles floating point operations.",
                dataset="電子計算機名詞",
            )

            self.assertEqual(
                [item["source_term"] for item in hits],
                ["floating-point", "compiler"],
            )
            self.assertEqual(hits[0]["target_term"], "浮點")

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            self.assertEqual(count, 2)

    def test_render_glossary_block_only_lists_hits(self):
        hits = [
            {"source_term": "floating-point", "target_term": "浮點"},
            {"source_term": "compiler", "target_term": "編譯器"},
        ]

        block = naer_terms.render_glossary_block(hits)

        self.assertIn("Terminology references for this chunk:", block)
        self.assertIn("- floating-point -> 浮點", block)
        self.assertIn("- compiler -> 編譯器", block)

    def test_detects_term_mismatches_against_translation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ods_path = self._create_sample_ods(temp_path)
            db_path = temp_path / "terms.sqlite3"
            naer_terms.import_ods_to_sqlite(
                ods_path,
                db_path,
                dataset="電子計算機名詞",
                domain="computer-science",
            )

            report = naer_terms.check_term_mismatches(
                db_path,
                source_text="A compiler uses floating-point arithmetic.",
                translated_text="一個編譯程式使用浮點運算。",
                dataset="電子計算機名詞",
            )

            self.assertEqual(report["matched_terms"], 2)
            self.assertEqual(report["mismatches"], 1)
            self.assertEqual(report["issues"][0]["source_term"], "compiler")
            self.assertEqual(report["issues"][0]["expected_target"], "編譯器")

    def test_normalize_term_folds_hyphens_and_case(self):
        self.assertEqual(
            naer_terms.normalize_term(" Floating-Point "),
            "floating point",
        )

    def test_query_avoids_false_positive_for_uppercase_acronym_and_symbol_term(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "terms.sqlite3"
            with sqlite3.connect(db_path) as conn:
                naer_terms._ensure_schema(conn)
                conn.execute(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("AND", "及；與", "and", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "sample.ods", "and-row"),
                )
                conn.execute(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("A#", "A# 代數系統", "a", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "sample.ods", "asharp-row"),
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "A compiler handles arithmetic and architecture.",
                dataset="電子計算機名詞",
            )

            self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
