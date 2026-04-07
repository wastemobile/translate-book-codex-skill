#!/usr/bin/env python3
"""Stage 3: refine draft translations with a larger local model provider."""

import argparse
import glob
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from local_model_client import (
    DEFAULT_OMLX_API_BASE,
    DEFAULT_PROVIDER,
    generate_text,
    read_text,
    write_text,
)
from naer_terms import find_glossary_hits, render_glossary_block


DEFAULT_MODEL = "gemma-4-26b-a4b-it-mxfp4"


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


def build_glossary_block(glossary_db, source_text, dataset=None, domain=None):
    if not glossary_db:
        return ""
    hits = find_glossary_hits(glossary_db, source_text, dataset=dataset, domain=domain)
    return render_glossary_block(hits)


def build_prompt(source_text, draft_text, target_lang, glossary_block=""):
    glossary_section = f"{glossary_block}\n\n" if glossary_block else ""
    return f"""Refine this draft translation into natural {target_lang}.
Be faithful to the source. Preserve markdown structure, links, image references, and footnotes.
Do not summarize, do not omit content, and do not reorganize the document.
If the draft is already correct, keep it close to the draft.
Output only the refined markdown.

{glossary_section}SOURCE:
{source_text}

DRAFT:
{draft_text}
"""


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
):
    glossary_block = build_glossary_block(
        glossary_db,
        source_text,
        dataset=glossary_dataset,
        domain=glossary_domain,
    )
    prompt = build_prompt(
        source_text,
        draft_text,
        target_lang,
        glossary_block=glossary_block,
    )
    return generate_text(
        prompt,
        model=model,
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        temperature=0.1,
    )


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
            ).strip()
            if not refined:
                raise ValueError("empty refinement")
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
):
    pending = discover_pending_refinements(temp_dir)
    report = {"pending": len(pending), "completed": 0, "failed": 0, "failures": []}
    if not pending:
        return report

    parallelism = max(1, min(int(parallelism), 3))
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
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--glossary-db")
    parser.add_argument("--glossary-dataset")
    parser.add_argument("--glossary-domain")
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
    )
    print(report)


if __name__ == "__main__":
    main()
