---
name: translate-book
description: Translate long-form books and ebooks (PDF, DOCX, EPUB) through a four-stage Codex plus local model workflow. Use when converting a book into Markdown chunks, generating baseline sample translations with Codex, running local `gemma-4-e4b-it-8bit` drafts, running local `gemma-4-26b-a4b-it-4bit` refinement, auditing high-risk chunks, and packaging final translated output back into HTML, DOCX, EPUB, and PDF with Pandoc and Calibre.
---

# Translate Book

Use this skill to translate an entire book with a conservative, resumable pipeline that preserves the original `translate-book` conversion and packaging flow while reducing large-model usage.

## Default Workflow

For normal usage, do not manually spell out each stage. Use the single entrypoint:

```bash
python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/run_book.py \
  --input-file "<file_path>" \
  --target-lang "zh-TW" \
  --output-formats "epub"
```

This entrypoint automatically:

- runs `preflight`
- uses `omlx` by default
- uses `http://127.0.0.1:8000/v1` by default
- uses `gemma-4-e4b-it-8bit` for Stage 2 unless overridden
- uses `gemma-4-26b-a4b-it-4bit` for Stage 3 unless overridden
- runs `convert -> draft -> refine -> audit --promote -> merge/build`
- stops immediately if preflight returns `fail`
- continues on `warn`, but should clearly report the warnings

Only override models, provider, API base, or formats if the user explicitly asks or the preflight result requires it.

## Requirements

- `python3`
- `pandoc`
- `ebook-convert`
- Python packages:
  - required: `pypandoc`
  - recommended: `beautifulsoup4`, `markdown`
  - optional: `opencc-python-reimplemented` for `zh-TW` regional lexicon normalization during audit
- Local model runtime:
  - default: `oMLX` at `http://127.0.0.1:8000/v1`
  - fallback: `Ollama` at `http://127.0.0.1:11434/api/generate`
- Recommended local models:
  - `gemma-4-e4b-it-8bit`
  - `gemma-4-26b-a4b-it-4bit`
- When using `oMLX`, keep these two models as the normal resident set and choose between them by stage:
  - `gemma-4-e4b-it-8bit` for Stage 2 draft speed
  - `gemma-4-26b-a4b-it-4bit` for Stage 3 refinement quality

`run_book.py` already performs preflight automatically. Run `preflight.py` directly only when you want to inspect environment problems before starting:

```bash
python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/preflight.py \
  --input-file "<file_path>" \
  --stage2-model gemma-4-e4b-it-8bit \
  --stage3-model gemma-4-26b-a4b-it-4bit \
  --api-base http://127.0.0.1:8000/v1 \
  --api-key "$LOCAL_LLM_API_KEY"
```

Do not start the low-level stage scripts manually if preflight returns `fail`.

## Collect Parameters

Determine these values from the user's request:

- `file_path`: source `pdf`, `docx`, or `epub`
- `target_lang`: default to `zh-TW` when the user asks for Traditional Chinese
- `output_formats`: ask the user which output format(s) they want; if not specified, default to the original source format
- `sample_count`: default `3`
- `parallelism`: default `1`, recommended ceiling `2`, hard ceiling `3`
- `custom_instructions`: optional translation style constraints

If the user did not provide a file path, ask for it.

## Manual Workflow

Use the following low-level stage commands only for debugging, resuming, or developing the skill itself. For ordinary translation work, prefer `scripts/run_book.py`.

### 1. Convert Source Book To Markdown Chunks

Run:

```bash
python3 scripts/convert.py "<file_path>" --olang "<target_lang>"
```

This creates a `*_temp/` directory containing:

- `input.html`
- `input.md`
- `chunk0001.md`, `chunk0002.md`, ...
- `manifest.json`
- `config.txt`

### 2. Create Baseline Sample Chunks With Codex

Select a small set of representative chunks for direct Codex translation.

Defaults:

- first 2 chunks
- 1 representative body chunk

Write those outputs to:

- `sample_chunk0001.md`
- `sample_chunk0002.md`
- ...

For any sample chunk that is already high quality, you may also use that text as the final `output_chunk*.md`.

### 3. Run Fast Local Draft Translation

Run:

```bash
python3 scripts/ollama_stage_translate.py --temp-dir "<temp_dir>" --target-lang "Traditional Chinese" --parallelism 1
```

This stage:

- reads `chunk*.md`
- skips chunks that already have `draft_chunk*.md`
- defaults to provider `omlx`
- uses model `gemma-4-e4b-it-8bit`
- writes `draft_chunk*.md`
- retries each failed chunk once

### 4. Run Local Refinement

Run:

```bash
python3 scripts/ollama_stage_refine.py --temp-dir "<temp_dir>" --target-lang "Traditional Chinese" --parallelism 1
```

This stage:

- reads `chunk*.md` plus `draft_chunk*.md`
- skips chunks that already have `refined_chunk*.md`
- defaults to provider `omlx`
- uses model `gemma-4-26b-a4b-it-4bit`
- writes `refined_chunk*.md`
- retries each failed chunk once

Provider overrides:

```bash
python3 scripts/ollama_stage_translate.py \
  --temp-dir "<temp_dir>" \
  --provider ollama \
  --api-base "http://127.0.0.1:11434/api/generate" \
  --model "<stage_2_model>"
```

The local model stages accept:

- `--provider`
- `--api-base`
- `--api-key`
- `--model`

Environment variable fallbacks:

- `LOCAL_LLM_PROVIDER`
- `LOCAL_LLM_API_BASE`
- `LOCAL_LLM_API_KEY`

### 5. Audit Refined Chunks

Run:

```bash
python3 scripts/chunk_audit.py --temp-dir "<temp_dir>" --promote
```

This stage:

- checks empty outputs
- checks suspiciously short outputs
- checks residual English
- checks basic Markdown mismatch signals
- promotes clean `refined_chunk*.md` into `output_chunk*.md`

### 6. Final Codex Review For High-Risk Chunks

Only use Codex directly for chunks that are still risky after audit, such as:

- chapter openings
- index, appendix, copyright, or table-of-contents chunks
- chunks flagged by audit
- chunks where the local model preserved too much English

Read:

- source `chunk*.md`
- `draft_chunk*.md`
- `refined_chunk*.md`
- relevant `sample_chunk*.md`

Then write the final result to `output_chunk*.md`.

### 7. Confirm Output Format(s)

If the user did not specify output formats, default to the original source format.

### 8. Merge And Build The Final Ebook

Run:

```bash
python3 scripts/merge_and_build.py --temp-dir "<temp_dir>" --title "<translated_title>" --formats "<requested_formats>"
```

The final merge/build stage still uses Pandoc and Calibre and produces:

- `output.md`
- `book.html`
- `book_doc.html`
- only the requested final book format(s), such as `book.epub` or `book.pdf`

If the original source is an `epub`, preserve its original cover image when building the translated `epub`.

## Chunk Lifecycle

- `chunk0001.md`: source
- `sample_chunk0001.md`: Codex baseline sample for a small number of chunks
- `draft_chunk0001.md`: stage-2 local draft
- `refined_chunk0001.md`: stage-3 local refinement
- `output_chunk0001.md`: final mergeable translation

## Parallelism

- Default parallelism: `1`
- Recommended maximum: `2`
- Absolute maximum: `3`
- Codex sample translation and final review stages should stay single-threaded

## Translation Rules

- Preserve Markdown structure exactly unless the source is plainly malformed.
- Preserve links, image references, footnotes, and bracketed markers.
- Do not summarize.
- Do not omit paragraphs.
- Do not add commentary outside translated content.
- Prefer natural Traditional Chinese when the target language is `zh-TW`.

## Heuristics

- Prefer single-thread execution unless quality and local model stability are already verified.
- Use Codex for style anchoring and difficult cleanup, not for full-book brute-force translation.
- If a refine-stage output is worse than the draft, keep the draft and mark the chunk for review.
- Do not overwrite final `output_chunk*.md` blindly if the user has manually edited it.

## References

- Use `scripts/convert.py` and `scripts/merge_and_build.py` as the source of truth for preprocessing and packaging.
- Use `scripts/chunk_audit.py` as the source of truth for suspicious-output heuristics and promotion rules.
