# translate-book-codex-skill

Version: `0.4.0`

Codex skill for translating whole books through a four-stage workflow:

`convert -> sample -> draft -> refine -> audit -> merge/build`

This repository is the development source for the locally installed skill at:

`~/.codex/skills/translate-book`

## What This Is

`translate-book-codex-skill` is a practical long-form translation workflow for whole books and ebooks.
It keeps the upstream conversion and packaging pipeline, but changes the translation orchestration into a mixed workflow:

- Codex handles a small number of representative sample chunks to anchor style and terminology.
- a fast local model produces first-pass translations chunk by chunk
- a stronger local model rewrites each draft into a cleaner and more consistent translation
- an audit stage promotes safe chunks and flags risky ones for manual or Codex review

The recommended interface is now a single entrypoint that performs preflight automatically:

```bash
$HOME/.codex/translate-book/.venv/bin/python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/run_book.py \
  --input-file ./novel.epub \
  --target-lang zh-TW \
  --output-formats epub
```

The manual stage-by-stage commands remain available for debugging and resume work, but they are no longer the primary path.

## Key Features

- single entrypoint with preflight before long translation runs
- four-stage translation pipeline: `sample -> draft -> refine -> audit`
- default local backend is `oMLX`, with `Ollama` retained as a fallback provider
- shared runtime under `~/.codex/translate-book/.venv`
- shared glossary DB under `~/.codex/translate-book/data/terms.sqlite3`
- NAER-backed glossary import, lookup, prompt injection, and mismatch audit
- `zh-TW` regional wording audit powered by OpenCC during the audit stage
- preserves intermediate files as `sample_`, `draft_`, `refined_`, and `output_`
- rebuilt translated `epub` files reuse the original source `epub` cover image

## Quick Start

### 1. Bootstrap the shared runtime

```bash
python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/bootstrap_shared_runtime.py \
  --seed-glossary-from /path/to/terms.sqlite3
```

This provisions:

- the shared Python runtime
- the shared glossary DB
- the global skill symlink:

```bash
~/.codex/skills/translate-book -> /Users/yoyodyne/lab/translate-book-codex-skill
```

### 2. Ask Codex to use the skill

Recommended prompt shape:

```text
請用 translate-book 技能把 ./book.epub 翻成繁體中文，輸出 epub 和 pdf
```

Another example:

```text
請用 translate-book 技能處理 ./source/book.pdf，目標語言 zh-TW，保留原書風格，只輸出 pdf
```

Include these details whenever possible:

- source file path
- target language
- output format or formats
- any style instructions

### 3. Or run the entrypoint directly

```bash
$HOME/.codex/translate-book/.venv/bin/python3 /Users/yoyodyne/lab/translate-book-codex-skill/scripts/run_book.py \
  --input-file ./book.epub \
  --target-lang zh-TW \
  --output-formats epub,pdf
```

Default behavior:

- provider: `omlx`
- API base: `http://127.0.0.1:8000/v1`
- Stage 2 model: `gemma-4-e4b-it-8bit`
- Stage 3 model: `gemma-4-26b-a4b-it-4bit`
- glossary DB: `~/.codex/translate-book/data/terms.sqlite3`
- pipeline: `preflight -> convert -> draft -> refine -> audit --promote -> merge/build`

## Workflow Overview

The current pipeline is best understood as:

`convert -> sample -> draft -> refine -> audit -> merge/build`

Stage responsibilities:

- `sample`: Codex translates a few representative chunks first, so the project has an initial style, tone, and terminology anchor
- `draft`: a fast local model produces first-pass translations chunk by chunk
- `refine`: a stronger local model rewrites each draft into a cleaner and more consistent translation
- `audit`: rule-based and reference-based checks decide which refined chunks are safe to promote, and which ones still need manual or Codex review

The conversion and packaging pipeline is inherited from the original `translate-book` workflow:

- Calibre `ebook-convert` converts source books into HTMLZ
- Pandoc converts HTML to Markdown and Markdown back to HTML
- validated chunks are merged and packaged into selected final formats such as `docx`, `epub`, or `pdf`
- when the source is an `epub`, the translated `epub` reuses the original cover image

## What Changed From Upstream

Compared with the upstream Claude version, this Codex version keeps the same preprocessing and packaging pipeline, but changes the translation orchestration:

- replaces the original high-concurrency subagent workflow with a conservative low-concurrency Codex workflow
- uses Codex itself only for a few sample chunks and final high-risk review
- adds a local-model draft stage, defaulting to `oMLX`, with `gemma-4-e4b-it-8bit`
- adds a local-model refinement stage, defaulting to `oMLX`, with `gemma-4-26b-a4b-it-4bit`
- adds `chunk_audit.py` to classify suspicious chunks and promote safe refined outputs
- preserves intermediate files as `sample_`, `draft_`, `refined_`, and `output_` instead of writing only one translation layer

## Output Formats

- the build step no longer assumes all of `docx`, `epub`, and `pdf`
- the default final output format is the original source file format
- you may request multiple formats, for example `epub,pdf`
- `book.html` and `book_doc.html` are still generated as intermediate or final HTML artifacts for packaging

Examples:

- source `book.epub` with no explicit format request: final default is `epub`
- source `book.pdf` with no explicit format request: final default is `pdf`
- explicit request `docx,epub`: generate both `book.docx` and `book.epub`

## Requirements

- shared Python runtime: `~/.codex/translate-book/.venv/bin/python3`
- `pandoc`
- `ebook-convert`
- required Python packages:
  - `pypandoc`
  - `beautifulsoup4`
  - `markdown`
  - `opencc-python-reimplemented`
- local model runtime:
  - default: `oMLX` at `http://127.0.0.1:8000/v1`
  - fallback: `Ollama` at `http://127.0.0.1:11434/api/generate`
- recommended local models:
  - `gemma-4-e4b-it-8bit`
  - `gemma-4-26b-a4b-it-4bit`
- shared glossary DB:
  - default: `~/.codex/translate-book/data/terms.sqlite3`

## Operational Notes

- if `~/.codex/skills/translate-book` points somewhere else, Codex may load an older copy of the skill
- a new Codex session is the safest way to ensure skill discovery sees a freshly updated symlink
- you should not install Python dependencies separately inside each book's working directory
- the shared runtime is the supported installation target for Python dependencies used by this skill
- if your local `oMLX` endpoint requires authentication, set `LOCAL_LLM_API_KEY` once in your shell profile instead of passing `--api-key` every time
- `LOCAL_LLM_PROVIDER`, `LOCAL_LLM_API_BASE`, and `LOCAL_LLM_API_KEY` are read automatically by the stage scripts and the preflight entrypoint
- if you override the Python interpreter with `TRANSLATE_BOOK_PYTHON`, make sure that interpreter can import `pypandoc`, `beautifulsoup4`, `markdown`, and `opencc`
- if you override the glossary path with `TRANSLATE_BOOK_GLOSSARY_DB`, make sure the file already exists before starting a long run

For `zh-TW` workflows:

- preflight fails if OpenCC is unavailable
- preflight fails if the shared glossary DB is missing

Only override values when needed, for example a custom model or different output formats.

## Preflight

The normal entrypoint is `scripts/run_book.py`. It automatically runs preflight before starting a long translation job.

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

For `zh-TW`, OpenCC is treated as a required dependency. If it is unavailable, preflight fails instead of silently skipping regional lexicon normalization.

## Contributors and Acknowledgments

Contributors:

- `wastemobile`: project direction, implementation, maintenance
- `OpenAI Codex / GPT`: code implementation, review assistance, documentation editing
- `Anthropic Claude Code`: prior review and documentation assistance

Upstream:

- original workflow: `deusyu/translate-book`
- upstream repository: https://github.com/deusyu/translate-book

## Third-Party Licenses

This project uses third-party software and data sources in the translation workflow, including OpenCC-related tooling and NAER terminology data.

OpenCC-related components:

- Python package used in the shared runtime: `opencc-python-reimplemented`
- Upstream OpenCC project: https://github.com/BYVoid/OpenCC
- OpenCC license: Apache License 2.0

NAER terminology data:

- Data source: National Academy for Educational Research (NAER) Term Search / 樂詞網
- Source site: https://terms.naer.edu.tw/
- Open data statement: https://terms.naer.edu.tw/mysite/about/2/
- Attribution note: use of NAER data should include source attribution
- project third-party license record: `./THIRD_PARTY_LICENSES.md`

When redistributing builds, packaged environments, or derived data artifacts that include these third-party components or source data, keep the applicable license, attribution, and notice obligations with that distribution.

## Repository Layout

- `SKILL.md`: Codex skill instructions
- `THIRD_PARTY_LICENSES.md`: third-party dependency and license record
- `scripts/`: conversion, translation-stage, audit, and packaging scripts
- `tests/`: unit tests for the vendored pipeline and provider-flexible local model stages
- `docs/superpowers/`: design specs and implementation plans

## Version 0.4.0

- default local model backend is now `oMLX`, with `Ollama` retained as a fallback provider
- Stage 2 and Stage 3 accept provider-aware local API configuration through CLI flags or environment variables
- developer test dependency setup now includes `requirements-dev.txt` for `pytest`
- rebuilt translated `epub` files now preserve the original source `epub` cover image
- shared Codex runtime support now uses a fixed venv under `~/.codex/translate-book/.venv`
- shared glossary DB support now defaults to `~/.codex/translate-book/data/terms.sqlite3`
- globally installed skill now points at this repository through `~/.codex/skills/translate-book`
- `run_book.py` and `merge_and_build.py` now use the shared runtime automatically instead of assuming the shell's `python3`
- `zh-TW` preflight now treats OpenCC and the shared glossary DB as required dependencies instead of silently degrading
- `run_book.py` and `preflight.py` now read `LOCAL_LLM_API_KEY` automatically when `--api-key` is omitted
- the default resident `oMLX` model pair is fixed to:
  - Stage 2 draft: `gemma-4-e4b-it-8bit`
  - Stage 3 refine: `gemma-4-26b-a4b-it-4bit`

Current local model policy:

- when running through `oMLX`, keep only two resident local models by default:
  - `gemma-4-e4b-it-8bit` for fast draft generation
  - `gemma-4-26b-a4b-it-4bit` for heavier refinement or difficult review work
- choose between them by stage and quality or cost tradeoff, rather than keeping a larger rotating model set loaded

## NAER Glossary V1

This repository includes a glossary v1 pipeline for importing NAER term downloads and using them as chunk-level translation references.

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
- name and place datasets should currently be treated as imported reference material, not as a fully tuned name-normalization system
- domain prioritization, ambiguity handling, and separate audit policies for names and places are still future work

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
  - intentionally kept separate from whole-text simplified or traditional conversion

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

## Manual Stage-by-Stage Flow

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

## Release Process

Versioning follows normal release tags in the form `vX.Y.Z`.

The repository includes a GitHub Actions workflow that creates a GitHub Release whenever a matching tag is pushed:

- example tag: `v0.4.0`
- source-of-truth version file: `VERSION`

For each future release:

1. update `VERSION`
2. update the version section in `README.md`
3. commit and push the release commit
4. create and push a tag such as `v0.5.0`

Once the tag reaches GitHub, the Releases tab should show the version normally.
