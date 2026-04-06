#!/usr/bin/env python3
"""Stage 2: create draft translations with a local model provider."""

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


DEFAULT_MODEL = "aya-expanse-8b-4bit-mlx"


def discover_pending_chunks(temp_dir):
    pending = []
    for source in sorted(glob.glob(os.path.join(temp_dir, "chunk*.md"))):
        draft = os.path.join(temp_dir, f"draft_{os.path.basename(source)}")
        if os.path.exists(draft):
            continue
        pending.append({"source": source, "draft": draft})
    return pending


def build_prompt(source_text, target_lang):
    return f"""Translate the following markdown into {target_lang}.
Preserve markdown structure, links, image references, and footnotes.
Do not summarize, omit content, or add commentary.
Output only the translated markdown.

SOURCE:
{source_text}
"""


def generate_translation(
    source_text,
    target_lang="Traditional Chinese",
    model=DEFAULT_MODEL,
    provider=DEFAULT_PROVIDER,
    api_base=DEFAULT_OMLX_API_BASE,
    api_key=None,
):
    prompt = build_prompt(source_text, target_lang)
    return generate_text(
        prompt,
        model=model,
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        temperature=0.2,
    )


def translate_one(item, target_lang, model, provider, api_base, api_key, max_attempts):
    source_text = read_text(item["source"])
    last_error = None
    for attempt in range(max_attempts):
        try:
            translated = generate_translation(
                source_text,
                target_lang=target_lang,
                model=model,
                provider=provider,
                api_base=api_base,
                api_key=api_key,
            ).strip()
            if not translated:
                raise ValueError("empty translation")
            write_text(item["draft"], translated)
            return True, item["draft"]
        except Exception as exc:  # pragma: no cover - exercised by tests through mocking
            last_error = exc
            if os.path.exists(item["draft"]):
                os.remove(item["draft"])
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
):
    pending = discover_pending_chunks(temp_dir)
    report = {"pending": len(pending), "completed": 0, "failed": 0, "failures": []}
    if not pending:
        return report

    parallelism = max(1, min(int(parallelism), 3))
    if parallelism == 1:
        for item in pending:
            ok, info = translate_one(
                item, target_lang, model, provider, api_base, api_key, max_attempts
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
                translate_one,
                item,
                target_lang,
                model,
                provider,
                api_base,
                api_key,
                max_attempts,
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
    parser = argparse.ArgumentParser(description="Create draft translations with a local model provider.")
    parser.add_argument("--temp-dir", required=True)
    parser.add_argument("--target-lang", default="Traditional Chinese")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--parallelism", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=2)
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
    )
    print(report)


if __name__ == "__main__":
    main()
