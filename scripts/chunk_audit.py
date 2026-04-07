#!/usr/bin/env python3
"""Audit refined chunks and optionally promote them to final outputs."""

import argparse
import glob
import os
import re
import shutil

from local_model_client import read_text
from naer_terms import auto_select_datasets, check_term_mismatches
from zh_variant_lexicon import normalize_with_opencc


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
    regional_lexicon_config=None,
    regional_lexicon_auto_fix=False,
    regional_lexicon_report=False,
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

    normalized_text = translated_text
    regional_auto_fixes = []
    regional_flagged_variants = []
    regional_opencc_available = None
    if regional_lexicon_config or regional_lexicon_auto_fix or regional_lexicon_report:
        regional_result = normalize_with_opencc(translated_text, config=regional_lexicon_config or "s2twp")
        regional_opencc_available = regional_result["opencc_available"]
        normalized_text = (
            regional_result["normalized_text"]
            if regional_lexicon_auto_fix
            else translated_text
        )
        regional_auto_fixes = regional_result["regional_auto_fixes"]
        regional_flagged_variants = regional_result["regional_flagged_variants"]
        if regional_flagged_variants:
            reasons.append("regional_lexicon")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "normalized_text": normalized_text,
        "regional_opencc_available": regional_opencc_available,
        "regional_auto_fixes": regional_auto_fixes,
        "regional_flagged_variants": regional_flagged_variants,
    }


def audit_temp_dir(
    temp_dir,
    promote=False,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
    regional_lexicon_config=None,
    regional_lexicon_auto_fix=False,
    regional_lexicon_report=False,
):
    report = {
        "checked": 0,
        "passed": 0,
        "failed": 0,
        "promoted": 0,
        "issues": [],
        "chunks": [],
        "regional_opencc_available": None,
    }
    for refined in sorted(glob.glob(os.path.join(temp_dir, "refined_chunk*.md"))):
        chunk_name = os.path.basename(refined).replace("refined_", "", 1)
        source = os.path.join(temp_dir, chunk_name)
        output = os.path.join(temp_dir, f"output_{chunk_name}")
        if not os.path.exists(source):
            report["failed"] += 1
            issue = {"source": source, "reasons": ["missing_source"], "regional_opencc_available": report["regional_opencc_available"]}
            report["issues"].append(issue)
            report["chunks"].append({"source": source, "refined": refined, "ok": False, **issue})
            continue

        result = audit_chunk(
            source,
            refined,
            glossary_db=glossary_db,
            glossary_dataset=glossary_dataset,
            glossary_domain=glossary_domain,
            glossary_auto_select=glossary_auto_select,
            glossary_auto_max_datasets=glossary_auto_max_datasets,
            regional_lexicon_config=regional_lexicon_config,
            regional_lexicon_auto_fix=regional_lexicon_auto_fix,
            regional_lexicon_report=regional_lexicon_report,
        )
        if result["regional_opencc_available"] is not None:
            report["regional_opencc_available"] = result["regional_opencc_available"]
        report["checked"] += 1
        chunk_entry = {
            "source": source,
            "refined": refined,
            "ok": result["ok"],
            "reasons": result["reasons"],
            "normalized_text": result["normalized_text"],
            "regional_opencc_available": result["regional_opencc_available"],
            "regional_auto_fixes": result["regional_auto_fixes"],
            "regional_flagged_variants": result["regional_flagged_variants"],
            "promoted": False,
        }
        if result["ok"]:
            report["passed"] += 1
            if promote:
                shutil.copyfile(refined, output)
                if regional_lexicon_auto_fix:
                    with open(output, "w", encoding="utf-8") as handle:
                        handle.write(result["normalized_text"])
                report["promoted"] += 1
                chunk_entry["promoted"] = True
        else:
            report["failed"] += 1
            report["issues"].append(
                {
                    "source": source,
                    "reasons": result["reasons"],
                    "normalized_text": result["normalized_text"],
                    "regional_opencc_available": result["regional_opencc_available"],
                    "regional_auto_fixes": result["regional_auto_fixes"],
                    "regional_flagged_variants": result["regional_flagged_variants"],
                }
            )
        report["chunks"].append(chunk_entry)
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
    parser.add_argument("--regional-lexicon-config")
    parser.add_argument("--regional-lexicon-auto-fix", action="store_true")
    parser.add_argument("--regional-lexicon-report", action="store_true")
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
            regional_lexicon_config=args.regional_lexicon_config,
            regional_lexicon_auto_fix=args.regional_lexicon_auto_fix,
            regional_lexicon_report=args.regional_lexicon_report,
        )
    )


if __name__ == "__main__":
    main()
