#!/usr/bin/env python3
"""Audit refined chunks and optionally promote them to final outputs."""

import argparse
import glob
import os
import re
import shutil

from local_model_client import read_text
from naer_terms import auto_select_datasets, check_term_mismatches


ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z]{4,}\b")


def _markdown_signal_count(text):
    return sum(
        [
            text.count("#"),
            text.count("]("),
            text.count("![]("),
            text.count("[^"),
        ]
    )


def audit_chunk(
    source_path,
    translated_path,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
):
    source_text = read_text(source_path)
    translated_text = read_text(translated_path)

    reasons = []
    stripped = translated_text.strip()
    if not stripped:
        reasons.append("empty")
    if stripped and len(stripped) < max(5, int(len(source_text.strip()) * 0.1)):
        reasons.append("too_short")

    english_words = ENGLISH_WORD_RE.findall(stripped)
    if stripped and len(english_words) >= 3:
        reasons.append("residual_english")

    source_markdown = _markdown_signal_count(source_text)
    translated_markdown = _markdown_signal_count(translated_text)
    if source_markdown and translated_markdown < max(0, source_markdown - 3):
        reasons.append("markdown_mismatch")

    if glossary_db:
        glossary_dataset_filter = glossary_dataset
        if glossary_auto_select and not glossary_dataset:
            glossary_dataset_filter = auto_select_datasets(
                glossary_db,
                source_text,
                dataset_candidates=None,
                domain=glossary_domain,
                max_datasets=glossary_auto_max_datasets,
            )
        mismatch_report = check_term_mismatches(
            glossary_db,
            source_text=source_text,
            translated_text=translated_text,
            dataset=glossary_dataset_filter,
            domain=glossary_domain,
            high_confidence_only=True,
        )
        if mismatch_report["mismatches"]:
            reasons.append("term_mismatch")

    return {"ok": not reasons, "reasons": reasons}


def audit_temp_dir(
    temp_dir,
    promote=False,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
):
    report = {"checked": 0, "passed": 0, "failed": 0, "promoted": 0, "issues": []}
    for refined in sorted(glob.glob(os.path.join(temp_dir, "refined_chunk*.md"))):
        chunk_name = os.path.basename(refined).replace("refined_", "", 1)
        source = os.path.join(temp_dir, chunk_name)
        output = os.path.join(temp_dir, f"output_{chunk_name}")
        if not os.path.exists(source):
            report["failed"] += 1
            report["issues"].append({"source": source, "reasons": ["missing_source"]})
            continue

        result = audit_chunk(
            source,
            refined,
            glossary_db=glossary_db,
            glossary_dataset=glossary_dataset,
            glossary_domain=glossary_domain,
            glossary_auto_select=glossary_auto_select,
            glossary_auto_max_datasets=glossary_auto_max_datasets,
        )
        report["checked"] += 1
        if result["ok"]:
            report["passed"] += 1
            if promote:
                shutil.copyfile(refined, output)
                report["promoted"] += 1
        else:
            report["failed"] += 1
            report["issues"].append({"source": source, "reasons": result["reasons"]})
    return report


def main():
    parser = argparse.ArgumentParser(description="Audit refined chunks before final merge.")
    parser.add_argument("--temp-dir", required=True)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--glossary-db")
    parser.add_argument("--glossary-dataset")
    parser.add_argument("--glossary-domain")
    parser.add_argument("--glossary-auto-select", action="store_true")
    parser.add_argument("--glossary-auto-max-datasets", type=int, default=2)
    args = parser.parse_args()
    print(
        audit_temp_dir(
            args.temp_dir,
            promote=args.promote,
            glossary_db=args.glossary_db,
            glossary_dataset=args.glossary_dataset,
            glossary_domain=args.glossary_domain,
            glossary_auto_select=args.glossary_auto_select,
            glossary_auto_max_datasets=args.glossary_auto_max_datasets,
        )
    )


if __name__ == "__main__":
    main()
