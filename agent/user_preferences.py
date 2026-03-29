"""
Extracts and merges cross-repo user patterns.
Deterministic aggregation — no extra AI calls needed.
"""

from collections import Counter
from . import context_store


def update_preferences(installation_id: int, owner: str, repo: str, understanding: dict):
    """Merge this repo's analysis into user-level shared preferences."""
    prefs = context_store.read_user_preferences(installation_id) or {
        "project_types": [],
        "repo_count": 0,
        "repos_analyzed": [],
    }

    full_name = f"{owner}/{repo}"
    if full_name not in prefs.get("repos_analyzed", []):
        prefs.setdefault("repos_analyzed", []).append(full_name)

    prefs["repo_count"] = len(prefs["repos_analyzed"])

    project_type = understanding.get("project_type")
    if project_type:
        prefs["project_types"].append(project_type)

    prefs["primary_project_type"] = _most_common(prefs["project_types"])

    context_store.write_user_preferences(installation_id, prefs)
    return prefs


def get_preference_summary(installation_id: int) -> str | None:
    """Build a short text summary for inclusion in AI prompts."""
    prefs = context_store.read_user_preferences(installation_id)
    if not prefs or prefs.get("repo_count", 0) == 0:
        return None

    lines = []
    lines.append(f"This user has {prefs['repo_count']} repo(s) analyzed.")

    if prefs.get("primary_project_type"):
        lines.append(f"Common project type: {prefs['primary_project_type']}")

    repos = prefs.get("repos_analyzed", [])
    if repos:
        lines.append(f"Other repos: {', '.join(repos[:5])}")

    return " ".join(lines)


def _most_common(items: list) -> str | None:
    if not items:
        return None
    counter = Counter(items)
    return counter.most_common(1)[0][0]
