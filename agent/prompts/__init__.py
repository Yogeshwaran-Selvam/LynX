from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(module: str, name: str) -> str:
    """Load a prompt file from agent/prompts/<module>/<name>.txt"""
    path = PROMPTS_DIR / module / f"{name}.txt"
    return path.read_text()
