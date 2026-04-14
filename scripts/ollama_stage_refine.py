#!/usr/bin/env python3
"""Stage 3: refine draft translations with a larger local model provider."""

import argparse
import glob
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from local_model_client import (
    DEFAULT_OMLX_API_BASE,
    DEFAULT_PROVIDER,
    generate_text,
    read_text,
    write_text,
)
from naer_terms import auto_select_datasets, check_term_mismatches, find_glossary_hits, render_glossary_block
from parallelism import resolve_parallelism
from style_prompts import load_style_prompt


DEFAULT_MODEL = "gemma-4-26b-a4b-it-8bit"


def discover_pending_refinements(temp_dir):
    pending = []
    for source in sorted(glob.glob(os.path.join(temp_dir, "chunk*.md"))):
        chunk_name = os.path.basename(source)
        draft = os.path.join(temp_dir, f"draft_{chunk_name}")
        refined = os.path.join(temp_dir, f"refined_{chunk_name}")
        if not os.path.exists(draft) or os.path.exists(refined):
            continue
        pending.append({"source": source, "draft": draft, "refined": refined})
    return pending


def build_glossary_block(glossary_db, source_text, dataset=None, domain=None, high_confidence_only=False):
    if not glossary_db:
        return ""
    hits = find_glossary_hits(
        glossary_db,
        source_text,
        dataset=dataset,
        domain=domain,
        high_confidence_only=high_confidence_only,
    )
    return render_glossary_block(hits, high_confidence_only=high_confidence_only)


def build_prompt(source_text, draft_text, target_lang, glossary_block="", genre="nonfiction", style_prompt_dir=None):
    glossary_section = f"{glossary_block}\n\n" if glossary_block else ""
    style_prompt = load_style_prompt("refine", genre=genre, prompt_dir=style_prompt_dir)
    return f"""{style_prompt}

Refine this draft translation into natural {target_lang}.
Be faithful to the source. Preserve markdown structure, links, image references, and footnotes.
Do not summarize, do not omit content, and do not reorganize the document.
If the draft is already correct, keep it close to the draft.
Output only the refined markdown.

{glossary_section}SOURCE:
{source_text}

DRAFT:
{draft_text}
"""


def build_repair_prompt(source_text, current_translation, issues, target_lang):
    issue = issues if isinstance(issues, dict) else issues[0]
    source_sentences = extract_relevant_source_excerpts(source_text, issue["source_term"])
    lines = [
        f"Fix only the terminology mismatches in this {target_lang} translation.",
        "Preserve markdown structure, wording, and paragraphing unless a mismatch requires a local edit.",
        "Do not rewrite the whole chunk. Only replace the mismatched term renderings.",
        "Return the complete repaired markdown only.",
        "Do not add explanations, notes, prefaces, or code fences.",
        "If no local edit is needed, return CURRENT TRANSLATION exactly unchanged.",
        "",
        "TERMINOLOGY FIX:",
    ]
    lines.append(f"- {issue['source_term']} -> {issue['expected_target']}")
    lines.extend(
        [
            "",
            "RELEVANT SOURCE EXCERPTS:",
            source_sentences,
            "",
            "CURRENT TRANSLATION:",
            current_translation,
        ]
    )
    return "\n".join(lines)


def extract_relevant_source_excerpts(source_text, source_term):
    sentences = re.split(r"(?<=[.!?])\s+", source_text.strip())
    term_pattern = re.compile(re.escape(source_term), re.IGNORECASE)
    matched = [sentence for sentence in sentences if term_pattern.search(sentence)]
    if matched:
        return "\n".join(matched[:2])
    return source_text[:400]


def sanitize_repair_output(candidate, current_translation):
    cleaned = candidate.strip()
    if not cleaned:
        return current_translation
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[^\n]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()

    first_anchor = next(
        (line.strip() for line in current_translation.splitlines() if line.strip()),
        "",
    )
    if first_anchor:
        position = cleaned.find(first_anchor)
        if position > 0:
            cleaned = cleaned[position:].strip()
    return cleaned or current_translation


def generate_refinement(
    source_text,
    draft_text,
    target_lang="Traditional Chinese",
    model=DEFAULT_MODEL,
    provider=DEFAULT_PROVIDER,
    api_base=DEFAULT_OMLX_API_BASE,
    api_key=None,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
    genre="nonfiction",
    style_prompt_dir=None,
):
    glossary_dataset_filter = glossary_dataset
    if glossary_db and glossary_auto_select and not glossary_dataset:
        glossary_dataset_filter = auto_select_datasets(
            glossary_db,
            source_text,
            dataset_candidates=None,
            domain=glossary_domain,
            max_datasets=glossary_auto_max_datasets,
        )
    glossary_block = build_glossary_block(
        glossary_db,
        source_text,
        dataset=glossary_dataset_filter,
        domain=glossary_domain,
        high_confidence_only=True,
    )
    prompt = build_prompt(
        source_text,
        draft_text,
        target_lang,
        glossary_block=glossary_block,
        genre=genre,
        style_prompt_dir=style_prompt_dir,
    )
    return generate_text(
        prompt,
        model=model,
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        temperature=0.1,
    )


def repair_terminology_mismatches(
    source_text,
    refined_text,
    target_lang="Traditional Chinese",
    model=DEFAULT_MODEL,
    provider=DEFAULT_PROVIDER,
    api_base=DEFAULT_OMLX_API_BASE,
    api_key=None,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
):
    if not glossary_db:
        return refined_text
    mismatch_report = check_term_mismatches(
        glossary_db,
        source_text=source_text,
        translated_text=refined_text,
        dataset=glossary_dataset,
        domain=glossary_domain,
        high_confidence_only=True,
    )
    if not mismatch_report["mismatches"]:
        return refined_text
    repaired = refined_text
    current_report = mismatch_report
    # Iterate current_report["issues"] on each pass so we always work from the
    # latest repaired state rather than the stale original issue list.
    max_passes = len(mismatch_report["issues"])
    for _ in range(max_passes):
        if not current_report["issues"]:
            break
        issue = current_report["issues"][0]
        prompt = build_repair_prompt(
            source_text,
            repaired,
            issue,
            target_lang,
        )
        candidate = generate_text(
            prompt,
            model=model,
            provider=provider,
            api_base=api_base,
            api_key=api_key,
            temperature=0.0,
        ).strip()
        if candidate:
            candidate = sanitize_repair_output(candidate, repaired)
            candidate_report = check_term_mismatches(
                glossary_db,
                source_text=source_text,
                translated_text=candidate,
                dataset=glossary_dataset,
                domain=glossary_domain,
                high_confidence_only=True,
            )
            if candidate_report["mismatches"] < current_report["mismatches"]:
                repaired = candidate
                current_report = candidate_report
                if not current_report["mismatches"]:
                    break
    return repaired


def refine_one(
    item,
    target_lang,
    model,
    provider,
    api_base,
    api_key,
    max_attempts,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
    repair_glossary_mismatches=False,
    genre="nonfiction",
    style_prompt_dir=None,
):
    source_text = read_text(item["source"])
    draft_text = read_text(item["draft"])
    last_error = None
    for attempt in range(max_attempts):
        try:
            refined = generate_refinement(
                source_text,
                draft_text,
                target_lang=target_lang,
                model=model,
                provider=provider,
                api_base=api_base,
                api_key=api_key,
                glossary_db=glossary_db,
                glossary_dataset=glossary_dataset,
                glossary_domain=glossary_domain,
                glossary_auto_select=glossary_auto_select,
                glossary_auto_max_datasets=glossary_auto_max_datasets,
                genre=genre,
                style_prompt_dir=style_prompt_dir,
            ).strip()
            if not refined:
                raise ValueError("empty refinement")
            if repair_glossary_mismatches:
                repair_dataset = glossary_dataset
                if glossary_db and glossary_auto_select and not glossary_dataset:
                    repair_dataset = auto_select_datasets(
                        glossary_db,
                        source_text,
                        dataset_candidates=None,
                        domain=glossary_domain,
                        max_datasets=glossary_auto_max_datasets,
                    )
                refined = repair_terminology_mismatches(
                    source_text,
                    refined,
                    target_lang=target_lang,
                    model=model,
                    provider=provider,
                    api_base=api_base,
                    api_key=api_key,
                    glossary_db=glossary_db,
                    glossary_dataset=repair_dataset,
                    glossary_domain=glossary_domain,
                )
            write_text(item["refined"], refined)
            return True, item["refined"]
        except Exception as exc:  # pragma: no cover - exercised by tests through mocking
            last_error = exc
            if os.path.exists(item["refined"]):
                os.remove(item["refined"])
            if attempt == max_attempts - 1:
                return False, str(last_error)
    return False, str(last_error)


def process_temp_dir(
    temp_dir,
    target_lang="Traditional Chinese",
    model=DEFAULT_MODEL,
    provider=DEFAULT_PROVIDER,
    api_base=DEFAULT_OMLX_API_BASE,
    api_key=None,
    parallelism=1,
    max_attempts=2,
    glossary_db=None,
    glossary_dataset=None,
    glossary_domain=None,
    glossary_auto_select=False,
    glossary_auto_max_datasets=2,
    repair_glossary_mismatches=False,
    genre="nonfiction",
    style_prompt_dir=None,
):
    pending = discover_pending_refinements(temp_dir)
    report = {"pending": len(pending), "completed": 0, "failed": 0, "failures": []}
    if not pending:
        return report

    parallelism = resolve_parallelism(parallelism)
    if parallelism == 1:
        for item in pending:
            ok, info = refine_one(
                item,
                target_lang,
                model,
                provider,
                api_base,
                api_key,
                max_attempts,
                glossary_db=glossary_db,
                glossary_dataset=glossary_dataset,
                glossary_domain=glossary_domain,
                glossary_auto_select=glossary_auto_select,
                glossary_auto_max_datasets=glossary_auto_max_datasets,
                repair_glossary_mismatches=repair_glossary_mismatches,
                genre=genre,
                style_prompt_dir=style_prompt_dir,
            )
            if ok:
                report["completed"] += 1
            else:
                report["failed"] += 1
                report["failures"].append({"source": item["source"], "error": info})
        return report

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {
            executor.submit(
                refine_one,
                item,
                target_lang,
                model,
                provider,
                api_base,
                api_key,
                max_attempts,
                glossary_db,
                glossary_dataset,
                glossary_domain,
                glossary_auto_select,
                glossary_auto_max_datasets,
                repair_glossary_mismatches,
                genre,
                style_prompt_dir,
            ): item
            for item in pending
        }
        for future in as_completed(futures):
            item = futures[future]
            ok, info = future.result()
            if ok:
                report["completed"] += 1
            else:
                report["failed"] += 1
                report["failures"].append({"source": item["source"], "error": info})
    return report


def main():
    parser = argparse.ArgumentParser(description="Refine draft translations with a local model provider.")
    parser.add_argument("--temp-dir", required=True)
    parser.add_argument("--target-lang", default="Traditional Chinese")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--parallelism", default="auto")
    parser.add_argument("--genre", choices=("fiction", "nonfiction"), default="nonfiction")
    parser.add_argument("--style-prompt-dir")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--glossary-db")
    parser.add_argument("--glossary-dataset")
    parser.add_argument("--glossary-domain")
    parser.add_argument("--glossary-auto-select", action="store_true")
    parser.add_argument("--glossary-auto-max-datasets", type=int, default=2)
    parser.add_argument("--repair-glossary-mismatches", action="store_true")
    args = parser.parse_args()

    report = process_temp_dir(
        args.temp_dir,
        target_lang=args.target_lang,
        model=args.model,
        provider=args.provider,
        api_base=args.api_base,
        api_key=args.api_key,
        parallelism=args.parallelism,
        max_attempts=args.max_attempts,
        glossary_db=args.glossary_db,
        glossary_dataset=args.glossary_dataset,
        glossary_domain=args.glossary_domain,
        glossary_auto_select=args.glossary_auto_select,
        glossary_auto_max_datasets=args.glossary_auto_max_datasets,
        repair_glossary_mismatches=args.repair_glossary_mismatches,
        genre=args.genre,
        style_prompt_dir=args.style_prompt_dir,
    )
    print(report)


if __name__ == "__main__":
    main()
