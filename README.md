# translate-book-codex-skill

Codex skill for translating whole books through a four-stage workflow:

1. Codex translates a few sample chunks as style and terminology anchors.
2. Local `aya-expanse:8b` generates fast draft translations.
3. Local `gemma4:26b` refines each chunk.
4. Codex reviews only high-risk chunks before final packaging.

The conversion and packaging pipeline is inherited from the original `translate-book` workflow:

- Calibre `ebook-convert` converts source books into HTMLZ
- Pandoc converts HTML to Markdown and Markdown back to HTML
- validated chunks are merged and packaged into `html`, `docx`, `epub`, and `pdf`

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
7. Run `scripts/merge_and_build.py`.

## Status

This repository is the development source for the locally installed skill at:

`~/.codex/skills/translate-book`
