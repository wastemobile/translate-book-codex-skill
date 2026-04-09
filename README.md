# translate-book-codex-skill

Version: `0.4.0`

Codex skill for translating whole books through a four-stage workflow.

The recommended interface is now a single entrypoint that performs preflight automatically:

```bash
$HOME/.codex/translate-book/.venv/bin/python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/run_book.py \
  --input-file ./novel.epub \
  --target-lang zh-TW \
  --output-formats epub
```

The manual stage-by-stage commands remain available for debugging and resume work, but they are no longer the primary path.

## Architecture Overview

The current pipeline is best understood as:

`convert -> sample -> draft -> refine -> audit -> merge/build`

With translation-specific stages grouped as:

`sample -> draft -> refine -> audit`

Stage responsibilities:

- `sample`: Codex translates a few representative chunks first, so the project has an initial style, tone, and terminology anchor.
- `draft`: a fast local model produces first-pass translations chunk by chunk.
- `refine`: a stronger local model rewrites each draft into a cleaner and more consistent translation.
- `audit`: rule-based and reference-based checks decide which refined chunks are safe to promote, and which ones still need manual or Codex review.

Current reference and normalization hooks:

- `sample`:
  - style and terminology anchoring is currently done manually through the selected sample chunks
  - glossary references are not yet automatically injected at this stage
- `draft`:
  - NAER-backed glossary lookup can inject chunk-level terminology references into the prompt
  - this is the main place where technical term standardization currently starts to take effect
- `refine`:
  - the same glossary lookup can be injected again, so terminology consistency is reinforced during rewriting
  - experimental glossary repair logic can attempt targeted terminology correction, but it should still be treated as non-final
- `audit`:
  - glossary mismatch checking can flag places where expected standard terms were not used
  - OpenCC-backed regional lexicon normalization can auto-fix high-confidence `zh-CN` wording into `zh-TW` wording and report lower-confidence findings

Current interpretation of standards support:

- terminology standards:
  - supported now through the NAER glossary pipeline
- personal-name and place-name standards:
  - these can already be imported into the same glossary database if they exist as NAER term packages
  - however, they are not yet handled with dedicated ranking, ambiguity rules, or audit policies distinct from domain terminology
- regional wording normalization:
  - supported now only at `audit`
  - intentionally kept separate from whole-text simplified/traditional conversion

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
- adds a local-model draft stage, defaulting to `oMLX`, with `gemma-4-e4b-it-8bit`
- adds a local-model refinement stage, defaulting to `oMLX`, with `gemma-4-26b-a4b-it-4bit`
- adds `chunk_audit.py` to classify suspicious chunks and promote safe refined outputs
- preserves intermediate files as `sample_`, `draft_`, `refined_`, and `output_` instead of writing only one translation layer

## Version 0.4.0

- default local model backend is now `oMLX`, with `Ollama` retained as a fallback provider
- Stage 2 and Stage 3 accept provider-aware local API configuration through CLI flags or environment variables
- developer test dependency setup now includes `requirements-dev.txt` for `pytest`
- rebuilt translated `epub` files now preserve the original source `epub` cover image
- shared Codex runtime support now uses a fixed venv under `~/.codex/translate-book/.venv`
- shared glossary DB support now defaults to `~/.codex/translate-book/data/terms.sqlite3`
- globally installed skill now points at this repository through `~/.codex/skills/translate-book`
- `run_book.py` and `merge_and_build.py` now use the shared runtime automatically instead of assuming the shell's `python3`
- `zh-TW` preflight now treats `OpenCC` and the shared glossary DB as required dependencies instead of silently degrading
- `run_book.py` and `preflight.py` now read `LOCAL_LLM_API_KEY` automatically when `--api-key` is omitted
- the default resident `oMLX` model pair is fixed to:
  - Stage 2 draft: `gemma-4-e4b-it-8bit`
  - Stage 3 refine: `gemma-4-26b-a4b-it-4bit`

Current local model policy:

- when running through `oMLX`, keep only two resident local models by default:
  - `gemma-4-e4b-it-8bit` for fast draft generation
  - `gemma-4-26b-a4b-it-4bit` for heavier refinement or difficult review work
- choose between them by stage and quality/cost tradeoff, rather than keeping a larger rotating model set loaded

## Credits

- Original workflow: `deusyu/translate-book`
- Codex port and implementation: wastemobile with OpenAI Codex

## Requirements

- shared Python runtime: `~/.codex/translate-book/.venv/bin/python3`
- `pandoc`
- `ebook-convert`
- Required Python packages:
  - `pypandoc`
  - `beautifulsoup4`
  - `markdown`
  - `opencc-python-reimplemented`
- Local model runtime:
  - default: `oMLX` at `http://127.0.0.1:8000/v1`
  - fallback: `Ollama` at `http://127.0.0.1:11434/api/generate`
- Recommended local models:
  - `gemma-4-e4b-it-8bit`
  - `gemma-4-26b-a4b-it-4bit`
- Shared glossary DB:
  - default: `~/.codex/translate-book/data/terms.sqlite3`

## Preflight

The normal entrypoint is now `scripts/run_book.py`. It automatically runs preflight before starting a long translation job.

Typical usage from any working directory:

```bash
$HOME/.codex/translate-book/.venv/bin/python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/run_book.py \
  --input-file ./novel.epub \
  --target-lang zh-TW \
  --output-formats epub
```

Default behavior:

- provider: `omlx`
- API base: `http://127.0.0.1:8000/v1`
- Stage 2 model: `gemma-4-e4b-it-8bit`
- Stage 3 model: `gemma-4-26b-a4b-it-4bit`
- glossary DB: `~/.codex/translate-book/data/terms.sqlite3`
- pipeline: `preflight -> convert -> draft -> refine -> audit --promote -> merge/build`

## Global Skill Setup

The intended day-to-day interface is no longer "remember a Python command". It is:

```text
請用 translate-book 技能把 ./book.epub 翻成繁體中文，輸出 epub
```

To make that work consistently from any `~/lab/...` book directory, keep the globally installed skill as a symlink to this repository:

```bash
~/.codex/skills/translate-book -> /Users/yoyodyne/lab/translate-book-codex-skill
```

This repository includes a bootstrap script that provisions the shared runtime, shared glossary DB, and the global skill symlink:

```bash
python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/bootstrap_shared_runtime.py \
  --seed-glossary-from /path/to/terms.sqlite3
```

Operational notes:

- if `~/.codex/skills/translate-book` points somewhere else, Codex may load an older copy of the skill
- a new Codex session is the safest way to ensure skill discovery sees a freshly updated symlink
- you should not install Python dependencies separately inside each book's working directory
- the shared runtime is the supported installation target for Python dependencies used by this skill

## User Notes

When actually translating books, pay attention to these operational requirements:

- for `zh-TW`, preflight now fails if `OpenCC` is unavailable
- for `zh-TW`, preflight now fails if the shared glossary DB is missing
- if your local `oMLX` endpoint requires authentication, set `LOCAL_LLM_API_KEY` once in your shell profile instead of passing `--api-key` every time
- `LOCAL_LLM_PROVIDER`, `LOCAL_LLM_API_BASE`, and `LOCAL_LLM_API_KEY` are read automatically by the stage scripts and the preflight entrypoint
- if you override the Python interpreter with `TRANSLATE_BOOK_PYTHON`, make sure that interpreter can import `pypandoc`, `beautifulsoup4`, `markdown`, and `opencc`
- if you override the glossary path with `TRANSLATE_BOOK_GLOSSARY_DB`, make sure the file already exists before starting a long run

Only override values when needed, for example a custom model or different output formats.

If you want to run the checks by themselves first, use:

```bash
$HOME/.codex/translate-book/.venv/bin/python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/preflight.py \
  --input-file ./book.epub \
  --stage2-model gemma-4-e4b-it-8bit \
  --stage3-model gemma-4-26b-a4b-it-4bit \
  --glossary-db "$HOME/.codex/translate-book/data/terms.sqlite3" \
  --require-opencc \
  --api-base http://127.0.0.1:8000/v1 \
  --api-key "$LOCAL_LLM_API_KEY"
```

This check verifies:

- the input file exists
- the current working directory is writable
- `pandoc` and `ebook-convert` are available
- required and optional Python modules are visible
- the local model API is reachable
- the requested Stage 2 and Stage 3 model IDs are actually exposed by the server
- the shared glossary DB exists
- the shared Python runtime has the required modules
For `zh-TW`, `OpenCC` is treated as a required dependency. If it is unavailable, preflight fails instead of silently skipping regional lexicon normalization.

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

Practical scope of glossary v1:

- technical terminology is the primary supported use case today
- scholar-name and place-name datasets can already be bulk-imported into the same SQLite glossary store
- name/place datasets should currently be treated as imported reference material, not as a fully tuned name-normalization system
- domain prioritization, ambiguity handling, and separate audit policies for names and places are still future work

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

Dependency note:

- `opencc-python-reimplemented` is part of the required shared runtime dependency set
- for `zh-TW` workflows, OpenCC is no longer treated as optional during preflight

For non-`zh-TW` workflows, the audit step can still degrade gracefully if OpenCC is missing. For `zh-TW`, the run should not start until OpenCC is available in the shared runtime.

## Current vs Pending

Implemented now:

- `sample -> draft -> refine -> audit` translation pipeline
- NAER `.ods/.zip -> SQLite` glossary import
- multi-dataset glossary lookup and auto-select
- glossary injection in `draft` and `refine`
- glossary mismatch detection in `audit`
- OpenCC-backed `zh-CN` to `zh-TW` regional wording normalization in `audit`
- high-confidence regional auto-fix plus low-confidence reporting

Not fully solved yet:

- automatic glossary injection in the `sample` stage
- dedicated handling rules for scholar names, person names, and place names
- stronger disambiguation when multiple glossary datasets can all match the same phrase
- a polished glossary repair path that reliably fixes mismatches on real books
- cleaner, narrower structured spans in `regional_auto_fixes`
- broader validation across more book types, not only the current technical and technology-history samples

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

## Release Process

Versioning now follows normal release tags in the form `vX.Y.Z`.

The repository includes a GitHub Actions workflow that creates a GitHub Release whenever a matching tag is pushed:

- example tag: `v0.4.0`
- source-of-truth version file: `VERSION`

For each future release:

1. update `VERSION`
2. update the version section in `README.md`
3. commit and push the release commit
4. create and push a tag such as `v0.5.0`

Once the tag reaches GitHub, the Releases tab should show the version normally.
