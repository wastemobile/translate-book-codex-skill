# Local Model Provider Flexibility Design

## Goal

Make the translation pipeline flexible about which local inference server it uses, with `oMLX` as the default and `Ollama` retained as a fallback.

## Scope

This change affects only the local-model stages:

- `scripts/ollama_stage_translate.py`
- `scripts/ollama_stage_refine.py`
- shared inference client code
- tests and skill documentation

The chunk lifecycle and overall four-stage translation workflow stay the same.

## Design

Add a new shared module:

- `scripts/local_model_client.py`

It will expose:

- file helpers currently living in `ollama_common.py`
- provider-aware text generation helpers
- defaults for `omlx` and `ollama`

Supported providers:

- `omlx`
  - default API base: `http://127.0.0.1:8000/v1`
  - default request path: `/chat/completions`
  - auth via bearer token
- `ollama`
  - default API URL: `http://127.0.0.1:11434/api/generate`
  - no auth by default

## Configuration Rules

Stage scripts will accept:

- `--provider`
- `--api-base`
- `--api-key`
- `--model`

Priority order:

1. CLI flags
2. environment variables
3. provider defaults in code

Environment variables:

- `LOCAL_LLM_PROVIDER`
- `LOCAL_LLM_API_BASE`
- `LOCAL_LLM_API_KEY`

## Script Behavior

Stage 2 and Stage 3 will call one shared `generate_text(...)` entrypoint.

Provider-specific behavior:

- `omlx` sends OpenAI-compatible chat requests and returns the first assistant message text
- `ollama` sends the existing generate request and returns `response`

Default provider: `omlx`

Default models remain stage-specific, but are updated to MLX-native names where appropriate:

- Stage 2 default: `aya-expanse-8b-4bit-mlx`
- Stage 3 default: `gemma-4-26b-a4b-it-mxfp4`

Users can still override model IDs explicitly.

## Non-Goals

- changing the Codex sample/final-review stages
- adding dynamic model discovery inside the scripts
- adding third-party hosted APIs

## Verification

Add tests for:

- provider default resolution
- OpenAI-compatible request formatting
- Ollama request formatting
- stage scripts inheriting the new defaults and passing provider config through
