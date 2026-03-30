"""
CI/CD YAML generator — uses a code-focused LLM to produce
production-grade GitHub Actions workflows from repo context.
"""

import os
import json
import logging
import yaml
from groq import Groq
from dotenv import load_dotenv
from .prompts import load_prompt

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logger = logging.getLogger(__name__)

# Code-focused models — different priority than the narrator
MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
]

# Files relevant to CI/CD generation
CI_RELEVANT_FILES = {
    "package.json", "package-lock.json", "requirements.txt", "pyproject.toml",
    "setup.py", "setup.cfg", "go.mod", "go.sum", "Cargo.toml", "Gemfile",
    "composer.json", "pom.xml", "build.gradle", "Makefile",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".flake8",
    "tsconfig.json", "jest.config.js", "pytest.ini", "tox.ini",
    ".github/workflows/ci.yml", ".github/workflows/cd.yml",
}


def _extract_key_files(repo_context: dict) -> str:
    """Extract only CI/CD-relevant file contents."""
    file_contents = repo_context.get("file_contents", {})
    lines = []
    total_chars = 0

    for path, content in file_contents.items():
        filename = path.split("/")[-1]
        if filename in CI_RELEVANT_FILES or path in CI_RELEVANT_FILES:
            chunk = content[:2000]
            lines.append(f"\n--- {path} ---")
            lines.append(chunk)
            total_chars += len(chunk)
            if total_chars > 6000:
                break

    return "\n".join(lines) if lines else "No dependency/config files found."


def _validate_yaml(yaml_string: str) -> bool:
    """Check if a YAML string parses without errors."""
    try:
        result = yaml.safe_load(yaml_string)
        return isinstance(result, dict) and "name" in result
    except yaml.YAMLError:
        return False


def _clean_response(raw: str) -> str:
    """Strip markdown fences and thinking tags."""
    # Strip thinking tags (qwen3)
    if "<think>" in raw:
        think_end = raw.find("</think>")
        if think_end != -1:
            raw = raw[think_end + 8:]

    raw = raw.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return raw


def _format_structured_context(structured: dict) -> str:
    """Format the deterministic structured context for the YAML prompt."""
    if not structured:
        return "No structured context available."
    lines = [f"Stack: {structured.get('stack', 'unknown')}"]
    if structured.get("project_name"):
        lines.append(f"Project name: {structured['project_name']}")
    lines.append(f"Has Docker: {structured.get('has_docker', False)}")
    lines.append(f"Has tests: {structured.get('has_tests', False)}")
    lines.append(f"Has lint config: {structured.get('has_lint', False)}")
    if structured.get("lint_tool"):
        lines.append(f"Lint tool: {structured['lint_tool']}")
    lines.append(f"Has lock file: {structured.get('has_lock_file', False)}")
    lines.append(f"Has existing CI: {structured.get('has_existing_ci', False)}")
    if structured.get("install_command"):
        lines.append(f"Install command: {structured['install_command']}")
    if structured.get("build_command"):
        lines.append(f"Build command: {structured['build_command']}")
    if structured.get("test_command"):
        lines.append(f"Test command: {structured['test_command']}")
    return "\n".join(lines)


def generate_yaml(repo_context: dict, understanding: dict) -> dict:
    """
    Generate CI and CD YAML files from repo context and AI understanding.
    Returns {"ci": "<yaml>", "cd": "<yaml>"}.
    """
    key_files = _extract_key_files(repo_context)
    tree = repo_context.get("tree_visual", "\n".join(repo_context.get("file_paths", [])))
    structured = repo_context.get("structured", {})

    system_prompt = load_prompt("yaml_generator", "system")
    user_message = load_prompt("yaml_generator", "user").format(
        core_idea=understanding.get("core_idea", "Unknown project"),
        the_flow=understanding.get("the_flow", "Unknown flow"),
        project_type=understanding.get("project_type", "unknown"),
        key_characters=", ".join(understanding.get("key_characters", [])),
        tree=tree,
        key_file_contents=key_files,
        structured_context=_format_structured_context(structured),
    )

    for model in MODELS:
        try:
            logger.info(f"  Trying model for YAML: {model}")
            logger.debug(f"Generating YAML with {model}")

            response = client.chat.completions.create(
                model=model,
                max_tokens=8000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            raw = _clean_response(raw)

            result = json.loads(raw)
            ci_yaml = result.get("ci", "")
            cd_yaml = result.get("cd", "")

            # Validate both
            if not _validate_yaml(ci_yaml):
                logger.warning(f"  {model}: CI YAML invalid")
                continue
            if not _validate_yaml(cd_yaml):
                logger.warning(f"  {model}: CD YAML invalid")
                continue

            logger.info(f"  {model}: Both YAML files valid")
            return {"ci": ci_yaml, "cd": cd_yaml, "model": model}

        except json.JSONDecodeError as e:
            logger.warning(f"  {model}: Invalid JSON — {e}")
            continue
        except Exception as e:
            logger.warning(f"  {model} failed: {e}")
            continue

    # All models failed — return minimal valid fallback
    logger.error("  All models failed YAML generation — using fallback")
    return {
        "ci": _fallback_ci(),
        "cd": _fallback_cd(),
        "model": "fallback",
        "error": "All models failed to produce valid YAML",
    }


def _fallback_ci() -> str:
    return """name: CI
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run build
        run: echo "Configure CI for your project"
"""


def _fallback_cd() -> str:
    return """name: CD
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main, master]
jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: echo "Configure deployment for your project"
"""
