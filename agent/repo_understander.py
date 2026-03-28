import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Priority files to explain in detail — the rest get one-liners
PRIORITY_FILES = {
    "package.json", "requirements.txt", "go.mod", "Dockerfile",
    "docker-compose.yml", "tsconfig.json", "pyproject.toml",
    ".github/workflows", "Makefile", "setup.py", "main.py",
    "app.py", "index.js", "server.js", "manage.py",
}


def _is_priority(path: str) -> bool:
    filename = path.split("/")[-1]
    return filename in PRIORITY_FILES or path in PRIORITY_FILES


def _prepare_context_for_groq(repo_data: dict) -> str:
    """
    Builds the text block sent to Groq.
    Includes tree + full content of priority files
    + truncated content of others.
    """
    lines = []
    lines.append(f"Repository: {repo_data['owner']}/{repo_data['repo']}")
    lines.append(f"\n## File Tree\n```\n{repo_data['tree_visual']}\n```")
    lines.append("\n## File Contents\n")

    for path, content in repo_data["file_contents"].items():
        lines.append(f"\n### {path}")
        if _is_priority(path):
            # Full content for important files
            lines.append(f"```\n{content[:3000]}\n```")
        else:
            # First 300 chars for secondary files
            lines.append(f"```\n{content[:300]}{'...' if len(content) > 300 else ''}\n```")

    return "\n".join(lines)


def understand_repo(repo_data: dict) -> dict:
    """
    Calls Groq to:
    1. Generate the core idea of this repo
    2. Generate a per-file explanation for every file

    Returns a dict ready to be used as CI/CD generation context.
    """
    context_text = _prepare_context_for_groq(repo_data)

    system_prompt = """You are an expert software engineer analyzing a GitHub repository. Your job is to deeply understand what this project does, how it is structured, and what each file's role is.

You must respond ONLY with a valid JSON object — no markdown, no backticks, no explanation outside the JSON.

The JSON must have this exact structure:
{
  "core_idea": "A clear 2-3 sentence summary of what this project does and its purpose",
  "stack": "The primary tech stack (e.g. 'Python/Django', 'Node.js/Express', 'Go')",
  "project_type": "One of: web-api, web-app, cli-tool, library, ml-project, data-pipeline, monorepo, other",
  "has_tests": true or false,
  "has_docker": true or false,
  "has_existing_ci": true or false,
  "build_commands": {
    "install": "command to install dependencies or null",
    "build": "command to build or null",
    "test": "command to run tests or null",
    "lint": "command to lint or null"
  },
  "file_explanations": {
    "path/to/file.py": "One sentence explaining what this file does and why it exists",
    "path/to/another.js": "One sentence explanation"
  },
  "key_entry_points": ["list", "of", "main", "entry", "point", "files"],
  "deployment_hints": "Any hints about how this app is deployed (e.g. 'Dockerized FastAPI, likely deployed to Kubernetes')"
}"""

    user_message = f"""Analyze this repository and return the JSON structure described.

{context_text}"""

    print("  🤖 Calling Groq to understand repository...")

    response = client.chat.completions.create(
        model="mixtral-8x7b-32768",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if Claude adds them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        understanding = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse failed: {e}")
        understanding = {
            "core_idea": "Could not parse repo understanding",
            "stack": "unknown",
            "raw_response": raw,
        }

    print(f"  ✅ Core idea: {understanding.get('core_idea', 'N/A')[:80]}...")
    return understanding
