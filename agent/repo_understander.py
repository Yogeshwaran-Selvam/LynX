import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv
from .prompts import load_prompt

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger = logging.getLogger(__name__)

# Models to try in order — llama-3.3-70b first (best at following "narrate every file"
# instruction), then llama-4-scout (highest TPM, good fallback for large repos),
# then smaller models.
MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
]


# ~4 chars per token on average. Groq free-tier lowest TPM is 6000.
# System prompt + tree + output budget = ~3000 tokens, leaving ~3000 for file content.
# Use 10000 chars (~2500 tokens) as a safe budget for file content.
MAX_CONTENT_CHARS = 10000

# Files that matter most for understanding a project — shown in full (or larger chunks)
_PRIORITY_NAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "go.mod", "Cargo.toml", "Gemfile", "composer.json", "pom.xml", "build.gradle",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "main.py", "app.py", "index.ts", "index.js", "server.ts", "server.js",
    "main.go", "main.rs", "lib.rs",
}


def _prepare_context(repo_context: dict) -> tuple[str, str]:
    """Build tree string and files content string from repo data.

    Strategy:
    - Structured context goes first (tiny, deterministic).
    - Priority files get larger chunks.
    - Remaining files get equal slices of whatever budget is left.
    - Total content is hard-capped at MAX_CONTENT_CHARS to avoid 413 errors.
    """
    tree = repo_context.get("tree_visual", "\n".join(repo_context.get("file_paths", [])))

    lines = []
    file_contents = repo_context.get("file_contents", repo_context.get("files_read", {}))

    # Add structured context as a reliable hint at the top
    structured = repo_context.get("structured")
    if structured:
        lines.append("--- Detected Project Info ---")
        lines.append(f"Stack: {structured.get('stack', 'unknown')}")
        if structured.get("project_name"):
            lines.append(f"Name: {structured['project_name']}")
        flags = []
        if structured.get("has_docker"):
            flags.append("Docker")
        if structured.get("has_tests"):
            flags.append("Tests")
        if structured.get("has_lint"):
            flags.append("Linting")
        if structured.get("has_existing_ci"):
            flags.append("Existing CI")
        if flags:
            lines.append(f"Has: {', '.join(flags)}")
        lines.append("")

    # Split files into priority and rest
    priority = {}
    rest = {}
    for path, content in file_contents.items():
        name = path.split("/")[-1]
        if name in _PRIORITY_NAMES:
            priority[path] = content
        else:
            rest[path] = content

    # Budget allocation: priority files get 40% of budget, rest get 60%
    priority_budget = int(MAX_CONTENT_CHARS * 0.4)
    rest_budget = MAX_CONTENT_CHARS - priority_budget

    # Add priority files
    total_used = 0
    if priority:
        per_priority = max(200, priority_budget // len(priority))
        for path, content in priority.items():
            chunk = content[:per_priority]
            entry = f"\n--- {path} ---\n{chunk}"
            lines.append(entry)
            total_used += len(entry)

    # Add remaining files with whatever budget is left
    actual_rest_budget = MAX_CONTENT_CHARS - total_used
    if rest and actual_rest_budget > 0:
        per_rest = max(80, actual_rest_budget // len(rest))
        for path, content in rest.items():
            if total_used >= MAX_CONTENT_CHARS:
                break
            chunk = content[:per_rest]
            entry = f"\n--- {path} ---\n{chunk}"
            lines.append(entry)
            total_used += len(entry)

    logger.info(f"  Context prepared: {len(file_contents)} files, {total_used} chars "
                f"({len(priority)} priority, {len(rest)} other)")
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
            logger.debug(f"Calling {model}")

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
