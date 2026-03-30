"""
PR creation flow — creates a branch, commits CI/CD YAML files,
and opens a pull request with a generated description.

Uses the GitHub Contents API (PUT /repos/.../contents/...) for file commits
instead of the Git Data API (trees/commits), because GitHub App installation
tokens with Contents:write can use Contents API but may be blocked on
the lower-level Git trees endpoint.
"""

import base64
import logging
import requests

from .repo_reader import _get_installation_token, _headers

logger = logging.getLogger(__name__)

BRANCH_NAME = "cicd-agent/setup-pipeline"
CI_PATH = ".github/workflows/ci.yml"
CD_PATH = ".github/workflows/cd.yml"


def _api(method: str, url: str, token: str, **kwargs) -> dict:
    """Helper — call GitHub API and return JSON or raise."""
    resp = getattr(requests, method)(url, headers=_headers(token), **kwargs)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _get_default_branch(token: str, owner: str, repo: str) -> tuple[str, str]:
    """Return (default_branch_name, sha) for the repo."""
    data = _api("get", f"https://api.github.com/repos/{owner}/{repo}", token)
    default_branch = data["default_branch"]
    ref = _api("get",
               f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{default_branch}",
               token)
    return default_branch, ref["object"]["sha"]


def _branch_exists(token: str, owner: str, repo: str) -> str | None:
    """Check if our branch already exists. Returns SHA or None."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{BRANCH_NAME}",
        headers=_headers(token),
    )
    if resp.status_code == 200:
        return resp.json()["object"]["sha"]
    return None


def _create_or_update_branch(token: str, owner: str, repo: str, base_sha: str) -> str:
    """Create the branch or force-update it to base_sha."""
    existing = _branch_exists(token, owner, repo)
    if existing:
        _api("patch",
             f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{BRANCH_NAME}",
             token, json={"sha": base_sha, "force": True})
        logger.info(f"  Updated existing branch {BRANCH_NAME} to {base_sha[:8]}")
        return base_sha
    else:
        _api("post",
             f"https://api.github.com/repos/{owner}/{repo}/git/refs",
             token, json={"ref": f"refs/heads/{BRANCH_NAME}", "sha": base_sha})
        logger.info(f"  Created branch {BRANCH_NAME} from {base_sha[:8]}")
        return base_sha


def _get_file_sha(token: str, owner: str, repo: str, path: str) -> str | None:
    """Get the SHA of an existing file on our branch (needed for updates)."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(token),
        params={"ref": BRANCH_NAME},
    )
    if resp.status_code == 200:
        return resp.json()["sha"]
    return None


def _commit_file(token: str, owner: str, repo: str,
                 path: str, content: str, message: str) -> dict:
    """Create or update a file via the Contents API."""
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": BRANCH_NAME,
    }
    # If file already exists on the branch, include its SHA (required for updates)
    existing_sha = _get_file_sha(token, owner, repo, path)
    if existing_sha:
        payload["sha"] = existing_sha

    return _api("put",
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                token, json=payload)


def _find_existing_pr(token: str, owner: str, repo: str) -> int | None:
    """Find an open PR from our branch. Returns PR number or None."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers=_headers(token),
        params={"head": f"{owner}:{BRANCH_NAME}", "state": "open"},
    )
    resp.raise_for_status()
    prs = resp.json()
    return prs[0]["number"] if prs else None


def _open_pr(token: str, owner: str, repo: str,
             default_branch: str, title: str, body: str) -> dict:
    """Open a PR or update the existing one. Returns PR data."""
    existing_pr = _find_existing_pr(token, owner, repo)

    if existing_pr:
        data = _api("patch",
                     f"https://api.github.com/repos/{owner}/{repo}/pulls/{existing_pr}",
                     token, json={"title": title, "body": body})
        logger.info(f"  Updated existing PR #{existing_pr}")
        return data

    data = _api("post",
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                token, json={
                    "title": title,
                    "head": BRANCH_NAME,
                    "base": default_branch,
                    "body": body,
                })
    logger.info(f"  Opened PR #{data['number']}")
    return data


def create_pr(installation_id: int, owner: str, repo: str,
              ci_yaml: str, cd_yaml: str, pr_body: str,
              structured: dict | None = None) -> dict:
    """
    Full PR creation flow:
    1. Get default branch SHA
    2. Create/update feature branch
    3. Commit ci.yml via Contents API
    4. Commit cd.yml via Contents API
    5. Open (or update) a PR

    Returns {"pr_number": int, "pr_url": str, "branch": str}.
    """
    token = _get_installation_token(installation_id)
    full_name = f"{owner}/{repo}"

    logger.info(f"[{full_name}] Creating PR...")

    # 1. Get base branch
    default_branch, base_sha = _get_default_branch(token, owner, repo)
    logger.info(f"  Base: {default_branch} @ {base_sha[:8]}")

    # 2. Create/reset feature branch
    _create_or_update_branch(token, owner, repo, base_sha)

    # 3. Commit CI file
    stack = structured.get("stack", "project") if structured else "project"
    ci_result = _commit_file(token, owner, repo, CI_PATH, ci_yaml,
                             f"ci: add CI workflow for {stack} project\n\nGenerated by LynX")
    logger.info(f"  Committed {CI_PATH}")

    # 4. Commit CD file
    cd_result = _commit_file(token, owner, repo, CD_PATH, cd_yaml,
                             f"ci: add CD workflow for {stack} project\n\nGenerated by LynX")
    commit_sha = cd_result["commit"]["sha"]
    logger.info(f"  Committed {CD_PATH} ({commit_sha[:8]})")

    # 5. Open or update PR
    title = "ci: Add CI/CD pipeline via LynX"
    pr_data = _open_pr(token, owner, repo, default_branch, title, pr_body)

    result = {
        "pr_number": pr_data["number"],
        "pr_url": pr_data["html_url"],
        "branch": BRANCH_NAME,
        "commit_sha": commit_sha,
    }
    logger.info(f"[{full_name}] PR ready: {result['pr_url']}")
    return result
