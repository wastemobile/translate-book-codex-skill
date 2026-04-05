# translate-book-codex-skill

Codex skill for translating whole books through a four-stage workflow:

1. Codex translates a few sample chunks as style and terminology anchors.
2. Local `aya-expanse:8b` generates fast draft translations.
3. Local `gemma4:26b` refines each chunk.
4. Codex reviews only high-risk chunks before final packaging.

The conversion and packaging pipeline is inherited from the original `translate-book` workflow:

- Calibre `ebook-convert` converts source books into HTMLZ
- Pandoc converts HTML to Markdown and Markdown back to HTML
- validated chunks are merged and packaged into selected final formats such as `docx`, `epub`, or `pdf`

## Upstream Reference

This project is based on the original Claude Code skill:

- `deusyu/translate-book`
- https://github.com/deusyu/translate-book

## What Changed

Compared with the upstream Claude version, this Codex version keeps the same preprocessing and packaging pipeline, but changes the translation orchestration:

- replaces the original high-concurrency subagent workflow with a conservative low-concurrency Codex workflow
- uses Codex itself only for a few sample chunks and final high-risk review
- adds a local Ollama draft stage with `aya-expanse:8b`
- adds a local Ollama refinement stage with `gemma4:26b`
- adds `chunk_audit.py` to classify suspicious chunks and promote safe refined outputs
- preserves intermediate files as `sample_`, `draft_`, `refined_`, and `output_` instead of writing only one translation layer

## Credits

- Original workflow: `deusyu/translate-book`
- Codex port and implementation: wastemobile with OpenAI Codex

## Requirements

- `python3`
- `pandoc`
- `ebook-convert`
- Python packages:
  - `pypandoc`
  - `beautifulsoup4` recommended
  - `markdown` recommended
- Local Ollama models:
  - `aya-expanse:8b`
  - `gemma4:26b`

## Repository Layout

- `SKILL.md`: Codex skill instructions
- `scripts/`: conversion, translation-stage, audit, and packaging scripts
- `tests/`: unit tests for the vendored pipeline and new Ollama stages
- `docs/superpowers/`: design spec and implementation plan

## Quick Flow

1. Run `scripts/convert.py` on a source `pdf`, `docx`, or `epub`.
2. Create a few `sample_chunk*.md` files with Codex.
3. Run `scripts/ollama_stage_translate.py`.
4. Run `scripts/ollama_stage_refine.py`.
5. Run `scripts/chunk_audit.py --promote`.
6. Let Codex fix flagged chunks into `output_chunk*.md`.
7. Choose output format(s). If you do not specify them, the default is the original source format.
8. Run `scripts/merge_and_build.py --formats "<format[,format...]>"`.

## Output Formats

- The build step no longer assumes all of `docx`, `epub`, and `pdf`.
- The default final output format is the original source file format.
- You may request multiple formats, for example `epub,pdf`.
- `book.html` and `book_doc.html` are still generated as intermediate/final HTML artifacts for packaging.

Examples:

- source `book.epub` with no explicit format request: final default is `epub`
- source `book.pdf` with no explicit format request: final default is `pdf`
- explicit request `docx,epub`: generate both `book.docx` and `book.epub`

## Status

This repository is the development source for the locally installed skill at:

`~/.codex/skills/translate-book`
