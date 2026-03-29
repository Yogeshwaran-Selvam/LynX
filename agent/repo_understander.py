import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv
from .prompts import load_prompt

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger = logging.getLogger(__name__)

# Models to try in order — best reasoning first, fallback if rate-limited
MODELS = [
    "qwen/qwen3-32b",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]


def _prepare_context(repo_context: dict) -> tuple[str, str]:
    """Build tree string and files content string from repo data."""
    tree = repo_context.get("tree_visual", "\n".join(repo_context.get("file_paths", [])))

    lines = []
    file_contents = repo_context.get("file_contents", repo_context.get("files_read", {}))
    num_files = len(file_contents)
    # Dynamically cap per-file size to fit within ~5000 token budget
    per_file_cap = max(500, min(4000, 20000 // max(num_files, 1)))
    for path, content in file_contents.items():
        lines.append(f"\n--- {path} ---")
        lines.append(content[:per_file_cap])

    return tree, "\n".join(lines)


def understand_repo(repo_context: dict, user_preferences: str | None = None) -> dict:
    """
    Calls Groq to narrate the repository — What, Why, How for every file.
    Tries multiple models, falls back on failure.
    """
    tree, files_content = _prepare_context(repo_context)

    system_prompt = load_prompt("repo_understander", "system")
    if user_preferences:
        system_prompt += f"\n\n## User Context\n{user_preferences}"

    user_message = load_prompt("repo_understander", "user").format(
        tree=tree,
        files_content=files_content,
    )

    # Try models in order
    for model in MODELS:
        try:
            logger.info(f"  Trying model: {model}")
            print(f"  🤖 Calling {model}...")

            response = client.chat.completions.create(
                model=model,
                max_tokens=8000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            # Strip thinking tags (qwen3 does this)
            if "<think>" in raw:
                think_end = raw.find("</think>")
                if think_end != -1:
                    raw = raw[think_end + 8:].strip()

            understanding = json.loads(raw)
            logger.info(f"  Model {model} succeeded")
            return understanding

        except json.JSONDecodeError as e:
            logger.warning(f"  {model} returned invalid JSON: {e}")
            logger.debug(f"  Raw response: {raw[:500]}")
            continue
        except Exception as e:
            logger.warning(f"  {model} failed: {e}")
            continue

    # All models failed
    logger.error("  All models failed to produce valid JSON")
    return {
        "core_idea": "Analysis could not be completed — all models failed",
        "file_narratives": {},
        "the_flow": "Unknown",
        "key_characters": [],
        "hidden_details": "None detected",
    }
