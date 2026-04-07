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

## NAER Glossary V1

This repository now includes a glossary v1 pipeline for importing NAER term downloads and using them as chunk-level translation references.

Script:

- `scripts/naer_terms.py`

Current capabilities:

- download a NAER `.zip` term package and extract the first `.ods`
- parse `.ods` sheet data into normalized term rows without requiring LibreOffice
- import those rows into a local `SQLite` glossary database
- query a Markdown chunk for matched glossary terms
- render a prompt-ready terminology block
- check a translated chunk for glossary mismatches
- inject glossary references into Stage 2 and Stage 3 prompts
- let `chunk_audit.py` flag `term_mismatch` cases during final review

Example flow:

```bash
python3 scripts/naer_terms.py download \
  --url "https://terms.naer.edu.tw/media/terms_data/1/..." \
  --out-dir ./test-output/naer

python3 scripts/naer_terms.py import \
  --ods ./test-output/naer/電子計算機名詞.ods \
  --db ./test-output/naer/terms.sqlite3 \
  --dataset "電子計算機名詞" \
  --domain "computer-science"

python3 scripts/naer_terms.py query \
  --db ./test-output/naer/terms.sqlite3 \
  --chunk ./sample_chunk.md \
  --dataset "電子計算機名詞" \
  --format prompt
```

The prototype uses a `reference + QA` policy:

- glossary hits are injected as translation references, not hard replacements
- post-translation checks flag `term_mismatch` cases where expected terminology was not used
- multiple datasets are supported through comma-separated dataset and domain filters, with left-to-right priority
- when `--glossary-auto-select` is enabled and no dataset is specified, the pipeline picks the top matching datasets for each chunk

Current recommendation:

- Stage 2 and Stage 3 glossary injection is usable
- glossary mismatch audit is usable
- glossary repair should still be treated as experimental until more real-book validation is completed

## Regional Lexicon Audit

This repository also includes an audit-stage regional lexicon normalization pass for `zh-CN` style wording in translated Chinese output.

What it does:

- uses OpenCC as the base lexicon source
- compares the translated chunk against an OpenCC-generated Taiwan-oriented candidate
- auto-applies only high-confidence localized replacements
- records low-confidence regional variants in the audit report
- keeps the behavior separate from full-text simplified-to-traditional conversion

What it does not do:

- it is not a Calibre plugin
- it is not a whole-text script conversion step
- it is not part of the Stage 2 or Stage 3 translation prompts

Example:

```bash
python3 scripts/chunk_audit.py \
  --temp-dir ./book_temp \
  --regional-lexicon-config s2twp \
  --regional-lexicon-auto-fix \
  --regional-lexicon-report
```

If OpenCC is not installed, the regional lexicon pass degrades gracefully and leaves the chunk unchanged while still returning a structured audit report.
That report includes a `regional_opencc_available` signal in the chunk-level and temp-dir summaries so you can see whether the backend was available when the report was generated.

Translation-stage integration:

```bash
python3 scripts/ollama_stage_translate.py \
  --temp-dir ./book_temp \
  --glossary-db ./test-output/naer/terms.sqlite3 \
  --glossary-dataset "電子計算機名詞" \
  --glossary-domain "computer-science"

python3 scripts/ollama_stage_refine.py \
  --temp-dir ./book_temp \
  --glossary-db ./test-output/naer/terms.sqlite3 \
  --glossary-dataset "電子計算機名詞" \
  --glossary-domain "computer-science"

python3 scripts/chunk_audit.py \
  --temp-dir ./book_temp \
  --glossary-db ./test-output/naer/terms.sqlite3 \
  --glossary-dataset "電子計算機名詞" \
  --glossary-domain "computer-science"
```

Multi-dataset example:

```bash
python3 scripts/ollama_stage_translate.py \
  --temp-dir ./book_temp \
  --glossary-db ./test-output/naer-multi/terms.sqlite3 \
  --glossary-auto-select \
  --glossary-auto-max-datasets 2 \
  --glossary-domain "computer-science,electrical-engineering"
```

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

## Recommended Invocation

When working in a directory that contains a source book, explicitly name the skill instead of relying on automatic intent detection.

Recommended prompt shape:

```text
請用 translate-book 技能把 ./book.epub 翻成繁體中文，輸出 epub 和 pdf
```

Include these details whenever possible:

- source file path
- target language
- output format or formats
- any style instructions

More examples:

```text
用 translate-book 技能翻譯目前目錄下的 novel.epub，目標語言 zh-TW，只輸出 epub
```

```text
請用 translate-book skill 處理 ./source/book.pdf，翻成繁體中文，保留原書風格，輸出 pdf
```

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
