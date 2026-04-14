"""Load stage- and genre-specific translation style prompts."""

from pathlib import Path


DEFAULT_STYLE_PROMPT_DIR = Path(__file__).resolve().parents[1] / "style_prompt"
VALID_GENRES = ("fiction", "nonfiction")
VALID_STAGES = ("draft", "refine")


def normalize_genre(genre):
    normalized = (genre or "nonfiction").strip().lower()
    if normalized == "nofiction":
        normalized = "nonfiction"
    if normalized not in VALID_GENRES:
        raise ValueError(f"unsupported genre: {genre}")
    return normalized


def load_style_prompt(stage, genre="nonfiction", prompt_dir=None):
    normalized_stage = (stage or "").strip().lower()
    if normalized_stage not in VALID_STAGES:
        raise ValueError(f"unsupported style prompt stage: {stage}")

    normalized_genre = normalize_genre(genre)
    base_dir = Path(prompt_dir) if prompt_dir else DEFAULT_STYLE_PROMPT_DIR
    path = base_dir / f"{normalized_genre}_{normalized_stage}.md"
    return path.read_text(encoding="utf-8").strip()
