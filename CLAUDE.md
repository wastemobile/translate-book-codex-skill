# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dev dependencies:**
```bash
pip install -r requirements-dev.txt
```

**Run all tests** (from repo root; tests add `scripts/` to `sys.path` automatically):
```bash
python -m pytest tests/
```

**Run a single test file:**
```bash
python -m pytest tests/test_chunk_audit.py
```

**Run the full translation pipeline** (normal usage):
```bash
python3 scripts/run_book.py \
  --input-file ./book.epub \
  --target-lang zh-TW \
  --output-formats epub
```

**Run preflight checks only:**
```bash
python3 scripts/preflight.py \
  --input-file ./book.epub \
  --stage2-model gemma-4-e4b-it-8bit \
  --stage3-model gemma-4-26b-a4b-it-4bit \
  --api-base http://127.0.0.1:8000/v1
```

**Run individual pipeline stages manually** (for debugging/resuming):
```bash
python3 scripts/convert.py "<file>" --olang zh-TW
python3 scripts/ollama_stage_translate.py --temp-dir ./book_temp --target-lang "Traditional Chinese"
python3 scripts/ollama_stage_refine.py   --temp-dir ./book_temp --target-lang "Traditional Chinese"
python3 scripts/chunk_audit.py           --temp-dir ./book_temp --promote
python3 scripts/merge_and_build.py       --temp-dir ./book_temp --lang zh-TW --formats epub
```

## Architecture

The pipeline is: `convert → draft → refine → audit --promote → merge/build`

`scripts/run_book.py` is the single orchestration entrypoint. It calls `preflight.py` first, aborts on `fail`, continues with a warning on `warn`, then subprocesses each stage script in order.

### Module relationships

- **`local_model_client.py`** — central LLM client; supports `omlx` (default, OpenAI-compatible `/chat/completions`) and `ollama` (`/api/generate`). Provider/endpoint resolved from CLI args, then `LOCAL_LLM_PROVIDER` / `LOCAL_LLM_API_BASE` / `LOCAL_LLM_API_KEY` env vars, then hardcoded defaults (`http://127.0.0.1:8000/v1` for oMLX).
- **`ollama_common.py`** — thin backward-compat wrapper around `local_model_client`; kept only for legacy imports.
- **`ollama_stage_translate.py`** — Stage 2 draft; reads `chunk*.md`, writes `draft_chunk*.md`; skips chunks that already have a draft. Default model: `gemma-4-e4b-it-mxfp8`.
- **`ollama_stage_refine.py`** — Stage 3 refinement; reads `chunk*.md` + `draft_chunk*.md`, writes `refined_chunk*.md`. Default model: `gemma-4-26b-a4b-it-mxfp4`.
- **`chunk_audit.py`** — audits `refined_chunk*.md` for empty, too-short, residual-English, and Markdown-mismatch signals; optionally runs NAER glossary mismatch and OpenCC regional lexicon checks; `--promote` copies passing chunks to `output_chunk*.md`.
- **`naer_terms.py`** — SQLite-backed NAER glossary; supports `.zip`/`.ods` import, chunk-level term lookup, prompt block rendering, and mismatch detection. Used by Stage 2, Stage 3, and audit.
- **`zh_variant_lexicon.py`** — OpenCC-backed `zh-CN → zh-TW` wording normalization (optional dep: `opencc-python-reimplemented`); used only during audit.
- **`manifest.py`** — writes/reads `manifest.json` in `*_temp/`; tracks chunk order and source SHA-256 hashes; `validate_for_merge` enforces all `output_chunk*.md` are present and source files are unchanged before merge.
- **`convert.py`** — calls Calibre `ebook-convert` to produce HTMLZ, then Pandoc to split into numbered `chunk*.md` files inside `*_temp/`.
- **`merge_and_build.py`** — concatenates `output_chunk*.md` in manifest order → `output.md` → `book.html`/`book_doc.html`; then calls `calibre_html_publish.py` for final `docx`/`epub`/`pdf` output. Preserves original EPUB cover image when source was EPUB.
- **`calibre_html_publish.py`** — thin Calibre wrapper that converts HTML to the requested output format(s).
- **`preflight.py`** — checks input file, writable CWD, `pandoc`/`ebook-convert` availability, required Python modules, local model API reachability, and that the requested Stage 2/3 model IDs are actually served.

### Chunk file lifecycle in `*_temp/`

```
chunk0001.md          ← source (from convert.py)
sample_chunk0001.md   ← optional Codex baseline sample
draft_chunk0001.md    ← Stage 2 local draft
refined_chunk0001.md  ← Stage 3 local refinement
output_chunk0001.md   ← final (promoted by audit or written by Codex review)
```

Each stage skips chunks that already have their output file, enabling safe resume.

### Key defaults

| Setting | Default |
|---|---|
| Provider | `omlx` |
| oMLX API base | `http://127.0.0.1:8000/v1` |
| Ollama API base | `http://127.0.0.1:11434/api/generate` |
| Stage 2 model | `gemma-4-e4b-it-8bit` |
| Stage 3 model | `gemma-4-26b-a4b-it-4bit` |
| Parallelism | `1` (recommended max `2`, hard ceiling `3`) |
| Output format | source file format |

### External tool dependencies

- **Calibre** (`ebook-convert`): source-format conversion and final ebook packaging. macOS path: `/Applications/calibre.app/Contents/MacOS/ebook-convert`.
- **Pandoc**: HTML-to-Markdown and Markdown-to-HTML conversion inside the pipeline.
- **OpenCC** (`opencc-python-reimplemented`): optional; required for `zh-TW` regional lexicon normalization in audit. Preflight returns `warn` (not `fail`) when absent.
