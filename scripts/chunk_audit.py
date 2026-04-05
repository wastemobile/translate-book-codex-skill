#!/usr/bin/env python3
"""Audit refined chunks and optionally promote them to final outputs."""

import argparse
import glob
import os
import re
import shutil

from ollama_common import read_text


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


def audit_chunk(source_path, translated_path):
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

    return {"ok": not reasons, "reasons": reasons}


def audit_temp_dir(temp_dir, promote=False):
    report = {"checked": 0, "passed": 0, "failed": 0, "promoted": 0, "issues": []}
    for refined in sorted(glob.glob(os.path.join(temp_dir, "refined_chunk*.md"))):
        chunk_name = os.path.basename(refined).replace("refined_", "", 1)
        source = os.path.join(temp_dir, chunk_name)
        output = os.path.join(temp_dir, f"output_{chunk_name}")
        if not os.path.exists(source):
            report["failed"] += 1
            report["issues"].append({"source": source, "reasons": ["missing_source"]})
            continue

        result = audit_chunk(source, refined)
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
    args = parser.parse_args()
    print(audit_temp_dir(args.temp_dir, promote=args.promote))


if __name__ == "__main__":
    main()
