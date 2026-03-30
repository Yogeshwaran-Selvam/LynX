"""
Full analysis pipeline: read repo -> AI narrate -> generate YAML -> save files.
Called from webhooks (background) and CLI (foreground).

Context is built once in Step 1 and sliced for each downstream phase:
- repo_context["structured"]  → deterministic stack/docker/test detection
- repo_context["file_contents"] → full file contents (understander truncates per-file)
- repo_context["tree_visual"]  → shared across all phases
The structured context is passed to both AI phases so the LLM has a reliable
anchor even if it would otherwise hallucinate the stack.
"""

import logging
import time

from .repo_reader import read_repo
from .repo_understander import understand_repo
from .yaml_generator import generate_yaml
from .pr_description import generate_pr_description
from .pr_creator import create_pr
from . import context_store
from .user_preferences import update_preferences, get_preference_summary

logger = logging.getLogger(__name__)


def analyze_repo(installation_id: int, owner: str, repo: str, force: bool = False) -> dict:
    """
    Full pipeline for a single repo. Each call is isolated —
    only touches this repo's context directory.
    """
    full_name = f"{owner}/{repo}"
    logger.info(f"[{full_name}] Starting analysis...")

    # Check if already analyzed recently
    if not force:
        meta = context_store.read_metadata(installation_id, owner, repo)
        if meta and meta.get("status") == "complete":
            logger.info(f"[{full_name}] Already analyzed, skipping (use force=True to re-analyze)")
            return context_store.read_repo_context(installation_id, owner, repo) or {}

    # Mark in-progress
    context_store.write_metadata(installation_id, owner, repo, {"status": "analyzing"})

    try:
        # Step 1 — Deep read all source files + extract structured context
        logger.info(f"[{full_name}] Step 1: Reading repo...")
        repo_context = read_repo(installation_id, owner, repo)
        tree_visual = repo_context["tree_visual"]
        structured = repo_context["structured"]
        logger.info(f"[{full_name}] Read {repo_context['total_files']} files")
        logger.info(f"[{full_name}] Stack: {structured['stack']} | "
                     f"Docker: {structured['has_docker']} | "
                     f"Tests: {structured['has_tests']} | "
                     f"Lint: {structured['has_lint']}")
        logger.info(f"[{full_name}] Tree:\n{tree_visual}")

        # Step 2 — AI narrative analysis (gets full files + structured hint)
        user_prefs = get_preference_summary(installation_id)
        logger.info(f"[{full_name}] Step 2: AI narrative analysis...")
        understanding = understand_repo(repo_context, user_preferences=user_prefs)

        narr_count = len(understanding.get("file_narratives", {}))
        logger.info(f"[{full_name}] Core idea: {understanding.get('core_idea', 'N/A')[:120]}")
        logger.info(f"[{full_name}] Narrated {narr_count} files")

        # Save narrative report to file
        context_store.save_narrative_report(
            installation_id, owner, repo, understanding, tree_visual
        )
        logger.info(f"[{full_name}] Saved report.txt")

        # Rate-limit pause before next Groq call
        time.sleep(3)

        # Step 3 — Generate CI/CD YAML (gets structured context + understanding)
        logger.info(f"[{full_name}] Step 3: Generating CI/CD YAML...")
        yaml_output = generate_yaml(repo_context, understanding)

        ci_lines = len(yaml_output.get("ci", "").split("\n"))
        cd_lines = len(yaml_output.get("cd", "").split("\n"))
        yaml_model = yaml_output.get("model", "unknown")
        logger.info(f"[{full_name}] Generated ci.yml ({ci_lines} lines) + cd.yml ({cd_lines} lines) via {yaml_model}")

        # Save YAML files
        context_store.save_yaml_files(installation_id, owner, repo, yaml_output)
        logger.info(f"[{full_name}] Saved ci.yml + cd.yml")

        if yaml_output.get("error"):
            logger.warning(f"[{full_name}] YAML warning: {yaml_output['error']}")

        # Step 4 — Generate PR description + create PR
        pr_result = None
        ci_yaml = yaml_output.get("ci", "")
        cd_yaml = yaml_output.get("cd", "")

        if ci_yaml and cd_yaml and not yaml_output.get("error"):
            # Rate-limit pause before next Groq call
            time.sleep(3)

            logger.info(f"[{full_name}] Step 4a: Generating PR description...")
            pr_body = generate_pr_description(ci_yaml, cd_yaml, understanding, structured)

            logger.info(f"[{full_name}] Step 4b: Creating branch + committing + opening PR...")
            try:
                pr_result = create_pr(
                    installation_id, owner, repo,
                    ci_yaml, cd_yaml, pr_body,
                    structured=structured,
                )
                logger.info(f"[{full_name}] PR created: {pr_result['pr_url']}")
            except Exception as e:
                logger.error(f"[{full_name}] PR creation failed: {e}", exc_info=True)
                pr_result = {"error": str(e)}
        else:
            logger.warning(f"[{full_name}] Skipping PR — YAML generation had errors")

        # Step 5 — Store encrypted full context (includes structured for future use)
        full_context = {
            "repo_context": {
                "owner": owner,
                "repo": repo,
                "file_paths": repo_context["file_paths"],
                "tree_visual": tree_visual,
                "total_files": repo_context["total_files"],
                "structured": structured,
            },
            "understanding": understanding,
            "yaml_output": yaml_output,
            "pr_result": pr_result,
        }
        context_store.write_repo_context(installation_id, owner, repo, full_context)

        # Step 6 — Update user preferences
        update_preferences(installation_id, owner, repo, understanding)

        # Step 7 — Mark complete (includes structured fields for quick lookup)
        metadata = {
            "status": "complete",
            "stack": structured["stack"],
            "has_docker": structured["has_docker"],
            "has_tests": structured["has_tests"],
            "core_idea": understanding.get("core_idea", "")[:300],
            "files_narrated": narr_count,
            "total_files_read": repo_context["total_files"],
            "yaml_generated": "error" not in yaml_output,
            "yaml_model": yaml_model,
            "ci_lines": ci_lines,
            "cd_lines": cd_lines,
        }
        if pr_result and "pr_url" in pr_result:
            metadata["pr_url"] = pr_result["pr_url"]
            metadata["pr_number"] = pr_result["pr_number"]
        context_store.write_metadata(installation_id, owner, repo, metadata)

        logger.info(f"[{full_name}] Analysis complete — all files saved")
        return full_context

    except Exception as e:
        logger.error(f"[{full_name}] Analysis failed: {e}", exc_info=True)
        context_store.write_metadata(installation_id, owner, repo, {
            "status": "failed",
            "error": str(e),
        })
        raise


def analyze_repos_batch(installation_id: int, repos: list[tuple[str, str]]):
    """
    Analyze multiple repos sequentially within a single background thread.
    Sequential to respect Groq free-tier rate limits.
    """
    logger.info(f"Batch analysis: {len(repos)} repo(s) for installation {installation_id}")

    for i, (owner, repo) in enumerate(repos):
        try:
            analyze_repo(installation_id, owner, repo, force=True)
        except Exception as e:
            logger.error(f"[{owner}/{repo}] Batch item failed: {e}")

        # Rate-limit pause between repos
        if i < len(repos) - 1:
            time.sleep(5)

    logger.info(f"Batch analysis complete for installation {installation_id}")
