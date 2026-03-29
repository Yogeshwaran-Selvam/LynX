"""
Full analysis pipeline: read repo -> AI narrate -> store context.
Called from webhooks (background) and CLI (foreground).
"""

import logging
import time

from .repo_reader import read_repo
from .repo_understander import understand_repo
from . import context_store
from .user_preferences import update_preferences, get_preference_summary

logger = logging.getLogger(__name__)


def _print_narrative(owner: str, repo: str, understanding: dict):
    """Print the full narrative to the console/logs."""
    full_name = f"{owner}/{repo}"
    divider = "=" * 60

    lines = [
        f"\n{divider}",
        f"  NARRATIVE: {full_name}",
        f"{divider}",
        f"\n📖 CORE IDEA:",
        f"  {understanding.get('core_idea', 'N/A')}",
        f"\n🔄 THE FLOW:",
        f"  {understanding.get('the_flow', 'N/A')}",
    ]

    # File narratives
    file_narratives = understanding.get("file_narratives", {})
    if file_narratives:
        lines.append(f"\n📁 FILE-BY-FILE NARRATIVE ({len(file_narratives)} files):")
        for path, bullets in file_narratives.items():
            lines.append(f"\n  ┌─ {path}")
            if isinstance(bullets, list):
                for bullet in bullets:
                    lines.append(f"  │  • {bullet}")
            else:
                lines.append(f"  │  • {bullets}")
            lines.append(f"  └{'─' * 40}")

    # Key characters
    key_chars = understanding.get("key_characters", [])
    if key_chars:
        lines.append(f"\n⭐ KEY FILES (the protagonists):")
        for f in key_chars:
            lines.append(f"  → {f}")

    # Hidden details
    hidden = understanding.get("hidden_details")
    if hidden:
        lines.append(f"\n🔍 HIDDEN DETAIL:")
        lines.append(f"  {hidden}")

    lines.append(f"\n{divider}\n")

    output = "\n".join(lines)
    print(output)
    logger.info(output)


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
        # Step 1 — Deep read all source files
        logger.info(f"[{full_name}] Step 1: Deep reading repo...")
        repo_context = read_repo(installation_id, owner, repo)
        logger.info(f"[{full_name}] Read {repo_context['total_files']} files")

        # Step 2 — Get user preferences for cross-repo context
        user_prefs = get_preference_summary(installation_id)

        # Step 3 — AI narrative analysis
        logger.info(f"[{full_name}] Step 2: AI narrative analysis...")
        understanding = understand_repo(repo_context, user_preferences=user_prefs)

        # Step 4 — Print the narrative
        _print_narrative(owner, repo, understanding)

        # Step 5 — Store encrypted context
        full_context = {
            "repo_context": {
                "owner": owner,
                "repo": repo,
                "file_paths": repo_context["file_paths"],
                "tree_visual": repo_context["tree_visual"],
                "total_files": repo_context["total_files"],
            },
            "understanding": understanding,
        }
        context_store.write_repo_context(installation_id, owner, repo, full_context)
        logger.info(f"[{full_name}] Context stored (encrypted)")

        # Step 6 — Update user preferences
        update_preferences(installation_id, owner, repo, understanding)

        # Step 7 — Mark complete
        context_store.write_metadata(installation_id, owner, repo, {
            "status": "complete",
            "core_idea": understanding.get("core_idea", "")[:300],
            "files_analyzed": len(understanding.get("file_narratives", {})),
            "total_files_read": repo_context["total_files"],
        })
        logger.info(f"[{full_name}] Analysis complete")

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
