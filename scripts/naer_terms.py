#!/usr/bin/env python3
"""Helpers and CLI for importing and querying NAER glossary data."""

import argparse
import json
import re
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}

HEADER_SOURCE_KEYS = ("英文", "英文名稱", "英語", "term", "english")
HEADER_TARGET_KEYS = ("中文", "中文名稱", "譯名", "chinese")
HEADER_NOTE_KEYS = ("備註", "註", "note", "remarks")
LOWERCASE_STOPWORD_TERMS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
}
GENERIC_SINGLE_WORD_TERMS = {
    "about",
    "account",
    "active",
    "additional",
    "alternative",
    "answer",
    "apparent",
    "arrival",
    "assistant",
    "attempt",
    "attendance",
    "augment",
    "attach",
    "area",
    "annual",
    "actual",
    "advanced",
    "appropriate",
    "accurately",
}


def _normalize_filter_values(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    values = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def normalize_term(text):
    normalized = re.sub(r"[-_/]+", " ", text.strip().lower())
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def download_file(url, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as response:
        destination.write_bytes(response.read())
    return destination


def extract_first_ods(zip_path, out_dir):
    zip_path = Path(zip_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".ods"):
                target = out_dir / Path(name).name
                target.write_bytes(archive.read(name))
                return target
    raise FileNotFoundError("no .ods file found in archive")


def _cell_text(cell):
    parts = []
    for paragraph in cell.findall(".//text:p", NS):
        parts.append("".join(paragraph.itertext()).strip())
    return " ".join(part for part in parts if part).strip()


def _expand_row_cells(row):
    cells = []
    for cell in row.findall("table:table-cell", NS):
        repeat = int(cell.attrib.get(f"{{{NS['table']}}}number-columns-repeated", "1"))
        text = _cell_text(cell)
        cells.extend([text] * repeat)
    return cells


def _classify_headers(header_cells):
    mapping = {"source": None, "target": None, "note": None}
    for index, value in enumerate(header_cells):
        lowered = value.strip().lower()
        if mapping["source"] is None and any(key in lowered for key in HEADER_SOURCE_KEYS):
            mapping["source"] = index
        elif mapping["target"] is None and any(key in lowered for key in HEADER_TARGET_KEYS):
            mapping["target"] = index
        elif mapping["note"] is None and any(key in lowered for key in HEADER_NOTE_KEYS):
            mapping["note"] = index
    return mapping


def parse_ods_rows(ods_path):
    ods_path = Path(ods_path)
    with zipfile.ZipFile(ods_path) as archive:
        content = archive.read("content.xml")

    root = ET.fromstring(content)
    rows = []
    for table in root.findall(".//table:table", NS):
        sheet_name = table.attrib.get(f"{{{NS['table']}}}name", "")
        table_rows = table.findall("table:table-row", NS)
        if not table_rows:
            continue
        header_cells = _expand_row_cells(table_rows[0])
        header_map = _classify_headers(header_cells)
        if header_map["source"] is None or header_map["target"] is None:
            continue

        for row in table_rows[1:]:
            cells = _expand_row_cells(row)
            source_term = cells[header_map["source"]].strip() if len(cells) > header_map["source"] else ""
            target_term = cells[header_map["target"]].strip() if len(cells) > header_map["target"] else ""
            if not source_term or not target_term:
                continue
            note = ""
            if header_map["note"] is not None and len(cells) > header_map["note"]:
                note = cells[header_map["note"]].strip()
            rows.append(
                {
                    "sheet_name": sheet_name,
                    "source_term": source_term,
                    "target_term": target_term,
                    "note": note,
                }
            )
    return rows


def _ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_term TEXT NOT NULL,
            target_term TEXT NOT NULL,
            normalized_source TEXT NOT NULL,
            domain TEXT,
            dataset TEXT,
            note TEXT,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            source_file TEXT,
            row_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_terms_lookup
        ON terms(normalized_source, dataset, domain)
        """
    )


def import_ods_to_sqlite(
    ods_path,
    db_path,
    dataset,
    domain,
    source_lang="en",
    target_lang="zh-TW",
):
    ods_path = Path(ods_path)
    db_path = Path(db_path)
    rows = parse_ods_rows(ods_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        for row in rows:
            normalized_source = normalize_term(row["source_term"])
            row_hash = "|".join(
                [
                    dataset,
                    domain,
                    row["sheet_name"],
                    normalized_source,
                    row["target_term"].strip(),
                ]
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO terms(
                    source_term,
                    target_term,
                    normalized_source,
                    domain,
                    dataset,
                    note,
                    source_lang,
                    target_lang,
                    source_file,
                    row_hash
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source_term"].strip(),
                    row["target_term"].strip(),
                    normalized_source,
                    domain,
                    dataset,
                    row["note"],
                    source_lang,
                    target_lang,
                    str(ods_path),
                    row_hash,
                ),
            )


def _build_filter_clause(column, values):
    if not values:
        return "", []
    placeholders = ", ".join(["?"] * len(values))
    return f"{column} IN ({placeholders})", list(values)


def _fetch_terms(conn, dataset=None, domain=None):
    query = "SELECT source_term, target_term, normalized_source, note, dataset, domain, priority FROM terms"
    clauses = []
    params = []
    dataset_values = _normalize_filter_values(dataset)
    domain_values = _normalize_filter_values(domain)
    if dataset_values:
        clause, clause_params = _build_filter_clause("dataset", dataset_values)
        clauses.append(clause)
        params.extend(clause_params)
    if domain_values:
        clause, clause_params = _build_filter_clause("domain", domain_values)
        clauses.append(clause)
        params.extend(clause_params)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY LENGTH(normalized_source) DESC, priority ASC, source_term ASC"
    terms = [
        {
            "source_term": row[0],
            "target_term": row[1],
            "normalized_source": row[2],
            "note": row[3],
            "dataset": row[4],
            "domain": row[5],
            "priority": row[6],
        }
        for row in conn.execute(query, params)
    ]
    dataset_order = {name: index for index, name in enumerate(dataset_values)}
    domain_order = {name: index for index, name in enumerate(domain_values)}
    terms.sort(
        key=lambda item: (
            dataset_order.get(item["dataset"], len(dataset_order)),
            domain_order.get(item["domain"], len(domain_order)),
            -len(item["normalized_source"]),
            item["priority"],
            item["source_term"],
        )
    )
    return terms


def auto_select_datasets(db_path, source_text, dataset_candidates=None, domain=None, max_datasets=2):
    dataset_values = _normalize_filter_values(dataset_candidates)
    if not dataset_values:
        with sqlite3.connect(db_path) as conn:
            dataset_values = [row[0] for row in conn.execute("SELECT DISTINCT dataset FROM terms ORDER BY dataset")]

    scored = []
    for index, dataset_name in enumerate(dataset_values):
        hits = find_glossary_hits(
            db_path,
            source_text,
            dataset=dataset_name,
            domain=domain,
            limit=100,
        )
        if not hits:
            continue
        scored.append(
            {
                "dataset": dataset_name,
                "hit_count": len(hits),
                "coverage": sum(len(item["normalized_source"]) for item in hits),
                "input_order": index,
            }
        )

    scored.sort(
        key=lambda item: (
            -item["hit_count"],
            item["input_order"],
            -item["coverage"],
        )
    )
    return [item["dataset"] for item in scored[: max(1, int(max_datasets))]]


def _term_matches_source(source_text, normalized_text, term):
    raw_term = term["source_term"].strip()
    normalized_source = term["normalized_source"]
    if not normalized_source or len(normalized_source) < 2:
        return False

    if raw_term.islower() and normalized_source in LOWERCASE_STOPWORD_TERMS:
        return False

    if "-" in raw_term:
        pieces = [re.escape(piece) for piece in raw_term.split("-") if piece]
        if not pieces:
            return False
        flags = 0 if any(ch.isupper() for ch in raw_term) else re.IGNORECASE
        pattern = r"[-\s]+".join(pieces)
        return re.search(rf"(?<!\w){pattern}(?!\w)", source_text, flags) is not None

    if raw_term.isupper() and len(raw_term) <= 5:
        return re.search(rf"(?<!\w){re.escape(raw_term)}(?!\w)", source_text) is not None

    if any(ch.isupper() for ch in raw_term):
        return re.search(rf"(?<!\w){re.escape(raw_term)}(?!\w)", source_text) is not None

    if re.search(r"[^A-Za-z0-9\s-]", raw_term):
        return re.search(rf"(?<!\w){re.escape(raw_term)}(?!\w)", source_text) is not None

    needle = f" {normalized_source} "
    return needle in normalized_text


def is_high_confidence_term(term):
    source_term = term["source_term"].strip()
    normalized_source = term["normalized_source"]

    if " " in normalized_source or "-" in source_term:
        return True
    if source_term.isupper() and len(source_term) >= 2:
        return True
    if re.search(r"[A-Z].*[A-Z]", source_term):
        return True
    if any(ch.isdigit() for ch in source_term):
        return True
    if re.search(r"[^A-Za-z0-9\s-]", source_term):
        return True
    if source_term[:1].isupper() and not source_term.isupper():
        return True
    if normalized_source in GENERIC_SINGLE_WORD_TERMS:
        return False
    return False


def find_glossary_hits(db_path, source_text, dataset=None, domain=None, limit=50, high_confidence_only=False):
    normalized_text = f" {normalize_term(source_text)} "
    with sqlite3.connect(db_path) as conn:
        terms = _fetch_terms(conn, dataset=dataset, domain=domain)
    hits = []
    seen = set()
    for term in terms:
        if high_confidence_only and not is_high_confidence_term(term):
            continue
        if _term_matches_source(source_text, normalized_text, term) and term["normalized_source"] not in seen:
            hits.append(term)
            seen.add(term["normalized_source"])
        if len(hits) >= limit:
            break
    return hits


def render_glossary_block(hits, high_confidence_only=False):
    if high_confidence_only:
        hits = [item for item in hits if is_high_confidence_term(item)]
    if not hits:
        return ""
    lines = ["Terminology references for this chunk:"]
    for item in hits:
        lines.append(f"- {item['source_term']} -> {item['target_term']}")
    lines.append("")
    lines.append(
        "Use these translations when the source term appears in this chunk unless context clearly requires a different sense."
    )
    return "\n".join(lines)


def check_term_mismatches(
    db_path,
    source_text,
    translated_text,
    dataset=None,
    domain=None,
    high_confidence_only=False,
):
    hits = find_glossary_hits(
        db_path,
        source_text,
        dataset=dataset,
        domain=domain,
        high_confidence_only=high_confidence_only,
    )
    issues = []
    for item in hits:
        if item["target_term"] not in translated_text:
            issues.append(
                {
                    "source_term": item["source_term"],
                    "expected_target": item["target_term"],
                }
            )
    return {
        "matched_terms": len(hits),
        "mismatches": len(issues),
        "issues": issues,
    }


def _cmd_download(args):
    zip_path = download_file(args.url, Path(args.out_dir) / Path(args.url).name)
    ods_path = extract_first_ods(zip_path, args.out_dir)
    print(json.dumps({"zip_path": str(zip_path), "ods_path": str(ods_path)}, ensure_ascii=False))


def _cmd_import(args):
    import_ods_to_sqlite(
        args.ods,
        args.db,
        dataset=args.dataset,
        domain=args.domain,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    print(json.dumps({"db": str(args.db), "dataset": args.dataset, "domain": args.domain}, ensure_ascii=False))


def _cmd_query(args):
    chunk_text = Path(args.chunk).read_text(encoding="utf-8")
    hits = find_glossary_hits(args.db, chunk_text, dataset=args.dataset, domain=args.domain, limit=args.limit)
    if args.format == "prompt":
        print(render_glossary_block(hits))
    else:
        print(json.dumps(hits, ensure_ascii=False, indent=2))


def _cmd_check(args):
    source_text = Path(args.source).read_text(encoding="utf-8")
    translated_text = Path(args.translated).read_text(encoding="utf-8")
    print(
        json.dumps(
            check_term_mismatches(
                args.db,
                source_text=source_text,
                translated_text=translated_text,
                dataset=args.dataset,
                domain=args.domain,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description="NAER glossary import and query helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--url", required=True)
    download_parser.add_argument("--out-dir", required=True)
    download_parser.set_defaults(func=_cmd_download)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--ods", required=True)
    import_parser.add_argument("--db", required=True)
    import_parser.add_argument("--dataset", required=True)
    import_parser.add_argument("--domain", required=True)
    import_parser.add_argument("--source-lang", default="en")
    import_parser.add_argument("--target-lang", default="zh-TW")
    import_parser.set_defaults(func=_cmd_import)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--db", required=True)
    query_parser.add_argument("--chunk", required=True)
    query_parser.add_argument("--dataset")
    query_parser.add_argument("--domain")
    query_parser.add_argument("--limit", type=int, default=50)
    query_parser.add_argument("--format", choices=("json", "prompt"), default="json")
    query_parser.set_defaults(func=_cmd_query)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--db", required=True)
    check_parser.add_argument("--source", required=True)
    check_parser.add_argument("--translated", required=True)
    check_parser.add_argument("--dataset")
    check_parser.add_argument("--domain")
    check_parser.set_defaults(func=_cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
