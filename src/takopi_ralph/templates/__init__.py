"""Prompt templates for Ralph loops."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


def load_template(name: str) -> str:
    """Load a template file by name."""
    template_path = TEMPLATES_DIR / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return template_path.read_text()
