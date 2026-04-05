---
name: translate-book
description: Translate long-form books and ebooks (PDF, DOCX, EPUB) through a four-stage Codex plus local Ollama workflow. Use when converting a book into Markdown chunks, generating baseline sample translations with Codex, running local `aya-expanse:8b` drafts, running local `gemma4:26b` refinement, auditing high-risk chunks, and packaging final translated output back into HTML, DOCX, EPUB, and PDF with Pandoc and Calibre.
---

# Translate Book

Use this skill to translate an entire book with a conservative, resumable pipeline that preserves the original `translate-book` conversion and packaging flow while reducing large-model usage.

## Requirements

- `python3`
- `pandoc`
- `ebook-convert`
- Python packages:
  - `pypandoc`
  - `beautifulsoup4` (recommended)
  - `markdown` (recommended)
- Local Ollama runtime for:
  - `aya-expanse:8b`
  - `gemma4:26b`

## Collect Parameters

Determine these values from the user's request:

- `file_path`: source `pdf`, `docx`, or `epub`
- `target_lang`: default to `zh-TW` when the user asks for Traditional Chinese
- `output_formats`: ask the user which output format(s) they want; if not specified, default to the original source format
- `sample_count`: default `3`
- `parallelism`: default `1`, recommended ceiling `2`, hard ceiling `3`
- `custom_instructions`: optional translation style constraints

If the user did not provide a file path, ask for it.

## End-To-End Workflow

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
- uses `aya-expanse:8b`
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
- uses `gemma4:26b`
- writes `refined_chunk*.md`
- retries each failed chunk once

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

Before the final build, ask the user which output format(s) they want.

Rules:

- default to the original source format
- if the source file is `epub`, default output is `epub`
- if the source file is `pdf`, default output is `pdf`
- if the source file is `docx`, default output is `docx`
- the user may request multiple formats, such as `epub,pdf`

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
