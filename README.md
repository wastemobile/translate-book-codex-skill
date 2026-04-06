# translate-book-codex-skill

Version: `0.2.0`

Codex skill for translating whole books through a four-stage workflow:

1. Codex translates a few sample chunks as style and terminology anchors.
2. Local `aya-expanse-8b-4bit-mlx` generates fast draft translations.
3. Local `gemma-4-26b-a4b-it-mxfp4` refines each chunk.
4. Codex reviews only high-risk chunks before final packaging.

The conversion and packaging pipeline is inherited from the original `translate-book` workflow:

- Calibre `ebook-convert` converts source books into HTMLZ
- Pandoc converts HTML to Markdown and Markdown back to HTML
- validated chunks are merged and packaged into selected final formats such as `docx`, `epub`, or `pdf`
- when the source is an `epub`, the translated `epub` reuses the original cover image

## Upstream Reference

This project is based on the original Claude Code skill:

- `deusyu/translate-book`
- https://github.com/deusyu/translate-book

## What Changed

Compared with the upstream Claude version, this Codex version keeps the same preprocessing and packaging pipeline, but changes the translation orchestration:

- replaces the original high-concurrency subagent workflow with a conservative low-concurrency Codex workflow
- uses Codex itself only for a few sample chunks and final high-risk review
- adds a local-model draft stage, defaulting to `oMLX`, with `aya-expanse-8b-4bit-mlx`
- adds a local-model refinement stage, defaulting to `oMLX`, with `gemma-4-26b-a4b-it-mxfp4`
- adds `chunk_audit.py` to classify suspicious chunks and promote safe refined outputs
- preserves intermediate files as `sample_`, `draft_`, `refined_`, and `output_` instead of writing only one translation layer

## Version 0.2.0

- default local model backend is now `oMLX`, with `Ollama` retained as a fallback provider
- Stage 2 and Stage 3 accept provider-aware local API configuration through CLI flags or environment variables
- developer test dependency setup now includes `requirements-dev.txt` for `pytest`
- rebuilt translated `epub` files now preserve the original source `epub` cover image

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
- Local model runtime:
  - default: `oMLX` at `http://127.0.0.1:8000/v1`
  - fallback: `Ollama` at `http://127.0.0.1:11434/api/generate`
- Recommended local models:
  - `aya-expanse-8b-4bit-mlx`
  - `gemma-4-26b-a4b-it-mxfp4`

## Repository Layout

- `SKILL.md`: Codex skill instructions
- `scripts/`: conversion, translation-stage, audit, and packaging scripts
- `tests/`: unit tests for the vendored pipeline and provider-flexible local model stages
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

Local stage overrides:

- default provider is `omlx`
- use `--provider ollama` to fall back to Ollama
- use `--api-base` and `--api-key` to point at a different local endpoint
- environment variables `LOCAL_LLM_PROVIDER`, `LOCAL_LLM_API_BASE`, and `LOCAL_LLM_API_KEY` are supported

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
