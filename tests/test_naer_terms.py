import io
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


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
    def test_derive_dataset_name_strips_suffixes(self):
        self.assertEqual(
            naer_terms.derive_dataset_name("外國地名譯名壓縮檔_VrsZ2AD.zip"),
            "外國地名譯名",
        )
        self.assertEqual(
            naer_terms.derive_dataset_name("圖書館學與資訊科學名詞壓縮檔.zip"),
            "圖書館學與資訊科學名詞",
        )

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
            result = naer_terms.import_ods_to_sqlite(
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
            self.assertEqual(result["rows_seen"], 2)
            self.assertEqual(result["rows_inserted"], 2)

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            self.assertEqual(count, 2)

    def test_import_zip_dir_to_sqlite_imports_multiple_archives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_dir = temp_path / "zips"
            zip_dir.mkdir()
            for name in [
                "圖書館學與資訊科學名詞壓縮檔.zip",
                "外國地名譯名壓縮檔_VrsZ2AD.zip",
            ]:
                with zipfile.ZipFile(zip_dir / name, "w") as archive:
                    archive.writestr("sample.ods", b"fake-ods")
                    archive.writestr("content.xml", ODS_CONTENT)
            db_path = temp_path / "terms.sqlite3"

            with mock.patch.object(naer_terms, "extract_first_ods") as extract_mock:
                with mock.patch.object(
                    naer_terms,
                    "import_ods_to_sqlite",
                    side_effect=[
                        {"dataset": "圖書館學與資訊科學名詞", "domain": "圖書館學與資訊科學名詞", "rows_seen": 2, "rows_inserted": 2, "ods_path": "a.ods"},
                        {"dataset": "外國地名譯名", "domain": "外國地名譯名", "rows_seen": 2, "rows_inserted": 2, "ods_path": "b.ods"},
                    ],
                ) as import_mock:
                    extract_mock.side_effect = [
                        temp_path / "a.ods",
                        temp_path / "b.ods",
                    ]
                    results = naer_terms.import_zip_dir_to_sqlite(zip_dir, db_path)

            self.assertEqual([item["dataset"] for item in results], ["圖書館學與資訊科學名詞", "外國地名譯名"])
            self.assertEqual(import_mock.call_args_list[0].kwargs["dataset"], "圖書館學與資訊科學名詞")
            self.assertEqual(import_mock.call_args_list[1].kwargs["dataset"], "外國地名譯名")

    def test_render_glossary_block_only_lists_hits(self):
        hits = [
            {"source_term": "floating-point", "target_term": "浮點"},
            {"source_term": "compiler", "target_term": "編譯器"},
        ]

        block = naer_terms.render_glossary_block(hits)

        self.assertIn("Terminology references for this chunk:", block)
        self.assertIn("- floating-point -> 浮點", block)
        self.assertIn("- compiler -> 編譯器", block)

    def test_render_glossary_block_high_confidence_filters_generic_single_words(self):
        hits = [
            {"source_term": "augmentation system", "target_term": "擴增系統", "normalized_source": "augmentation system", "dataset": "電子計算機名詞", "domain": "computer-science", "priority": 100, "note": ""},
            {"source_term": "Approach", "target_term": "Approach資料庫軟體", "normalized_source": "approach", "dataset": "電子計算機名詞", "domain": "computer-science", "priority": 100, "note": ""},
            {"source_term": "assistant", "target_term": "助理", "normalized_source": "assistant", "dataset": "電子計算機名詞", "domain": "computer-science", "priority": 100, "note": ""},
        ]

        block = naer_terms.render_glossary_block(hits, high_confidence_only=True)

        self.assertIn("augmentation system", block)
        self.assertIn("Approach", block)
        self.assertNotIn("assistant", block)

    def test_find_glossary_hits_can_return_only_high_confidence_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "terms.sqlite3"
            with sqlite3.connect(db_path) as conn:
                naer_terms._ensure_schema(conn)
                conn.executemany(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("augmentation system", "擴增系統", "augmentation system", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "augmentation-system"),
                        ("Approach", "Approach資料庫軟體", "approach", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "approach-product"),
                        ("assistant", "助理", "assistant", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "assistant-generic"),
                    ],
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "The augmentation system used Approach and an assistant.",
                dataset="電子計算機名詞",
                high_confidence_only=True,
            )

            self.assertEqual(
                [item["source_term"] for item in hits],
                ["augmentation system", "Approach"],
            )

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

    def test_query_avoids_false_positive_for_mixed_case_hyphenated_term(self):
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
                    ("A-law", "A 法則", "a law", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "sample.ods", "a-law-row"),
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "The company had a law against carrying radios on site.",
                dataset="電子計算機名詞",
            )

            self.assertEqual(hits, [])

    def test_query_supports_multiple_datasets_with_preferred_order(self):
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
                    ("bus", "匯流排", "bus", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "bus-cs"),
                )
                conn.execute(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("bus", "母線", "bus", "electrical-engineering", "電機工程名詞", "", "en", "zh-TW", 100, "b.ods", "bus-ee"),
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "The bus is overloaded.",
                dataset=["電機工程名詞", "電子計算機名詞"],
            )

            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["dataset"], "電機工程名詞")
            self.assertEqual(hits[0]["target_term"], "母線")

    def test_query_accepts_comma_separated_dataset_filter(self):
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
                    ("compiler", "編譯器", "compiler", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "compiler-cs"),
                )
                conn.execute(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("relay", "繼電器", "relay", "electrical-engineering", "電機工程名詞", "", "en", "zh-TW", 100, "b.ods", "relay-ee"),
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "A compiler drives a relay.",
                dataset="電子計算機名詞,電機工程名詞",
            )

            self.assertEqual(
                [item["source_term"] for item in hits],
                ["compiler", "relay"],
            )

    def test_query_ignores_common_lowercase_stopword_terms(self):
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
                    ("and", "及", "and", "electrical-engineering", "電機工程名詞", "", "en", "zh-TW", 100, "b.ods", "and-ee"),
                )

            hits = naer_terms.find_glossary_hits(
                db_path,
                "architecture and arithmetic",
                dataset="電機工程名詞",
            )

            self.assertEqual(hits, [])

    def test_auto_select_datasets_prefers_more_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "terms.sqlite3"
            with sqlite3.connect(db_path) as conn:
                naer_terms._ensure_schema(conn)
                conn.executemany(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("compiler", "編譯器", "compiler", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "compiler-cs"),
                        ("architecture", "架構", "architecture", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "architecture-cs"),
                        ("relay", "繼電器", "relay", "electrical-engineering", "電機工程名詞", "", "en", "zh-TW", 100, "b.ods", "relay-ee"),
                    ],
                )

            selected = naer_terms.auto_select_datasets(
                db_path,
                "The compiler architecture does not use a relay.",
                dataset_candidates=["電機工程名詞", "電子計算機名詞"],
                max_datasets=2,
            )

            self.assertEqual(selected, ["電子計算機名詞", "電機工程名詞"])

    def test_auto_select_datasets_can_limit_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "terms.sqlite3"
            with sqlite3.connect(db_path) as conn:
                naer_terms._ensure_schema(conn)
                conn.executemany(
                    """
                    INSERT INTO terms(
                        source_term, target_term, normalized_source, domain, dataset,
                        note, source_lang, target_lang, priority, source_file, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("bus", "匯流排", "bus", "computer-science", "電子計算機名詞", "", "en", "zh-TW", 100, "a.ods", "bus-cs"),
                        ("relay", "繼電器", "relay", "electrical-engineering", "電機工程名詞", "", "en", "zh-TW", 100, "b.ods", "relay-ee"),
                    ],
                )

            selected = naer_terms.auto_select_datasets(
                db_path,
                "The bus connects to a relay.",
                dataset_candidates="電子計算機名詞,電機工程名詞",
                max_datasets=1,
            )

            self.assertEqual(selected, ["電子計算機名詞"])


if __name__ == "__main__":
    unittest.main()
