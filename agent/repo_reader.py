import os
import base64
import time
import jwt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")

# Files to skip — binaries, lock files, noise
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff",
    ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz",
    ".lock", ".min.js", ".min.css",
}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
}

MAX_FILE_SIZE_BYTES = 50_000  # skip files larger than 50KB


# ── Auth ──────────────────────────────────────────────────────

def _get_jwt_token():
    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key = f.read()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": GITHUB_APP_ID}
    return jwt.encode(payload, private_key, algorithm="RS256")


def _get_installation_token(installation_id: int) -> str:
    jwt_token = _get_jwt_token()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


# ── File tree via Git Trees API (fastest — one API call) ──────

def _fetch_full_tree(token: str, owner: str, repo: str) -> list:
    """
    Uses GitHub's Git Trees API with recursive=1 to get
    the ENTIRE file tree in a single API call.
    Returns a flat list of file paths.
    """
    # First get the default branch's latest commit SHA
    repo_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_headers(token),
    )
    repo_resp.raise_for_status()
    default_branch = repo_resp.json()["default_branch"]

    branch_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}",
        headers=_headers(token),
    )
    branch_resp.raise_for_status()
    tree_sha = branch_resp.json()["commit"]["commit"]["tree"]["sha"]

    # Recursive tree fetch — one call for everything
    tree_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}",
        headers=_headers(token),
        params={"recursive": "1"},
    )
    tree_resp.raise_for_status()
    tree_data = tree_resp.json()

    files = []
    for item in tree_data.get("tree", []):
        if item["type"] != "blob":  # skip directories
            continue

        path = item["path"]
        size = item.get("size", 0)

        # Skip noise
        parts = path.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        _, ext = os.path.splitext(path)
        if ext.lower() in SKIP_EXTENSIONS:
            continue
        if size > MAX_FILE_SIZE_BYTES:
            continue

        files.append({"path": path, "size": size})

    return files


# ── Per-file content fetch ────────────────────────────────────

def _fetch_file_content(token: str, owner: str, repo: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(token))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None
    return None


# ── Build structured file map ─────────────────────────────────

def _build_tree_visual(file_paths: list) -> str:
    """
    Converts a flat list of paths into a visual tree string like:
    src/
      app/
        views.py
        models.py
      utils.py
    """
    tree = {}
    for path in file_paths:
        parts = path.split("/")
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    lines = []

    def render(node, prefix=""):
        for i, (key, subtree) in enumerate(sorted(node.items())):
            is_last = i == len(node) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{key}")
            if subtree:
                extension = "    " if is_last else "│   "
                render(subtree, prefix + extension)

    render(tree)
    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────

def read_repo(installation_id: int, owner: str, repo: str) -> dict:
    """
    Pulls the full repo:
    - Complete file tree
    - Each file's content individually (parallel)
    - Visual tree representation
    - Raw files dict for Claude to reason about
    """
    token = _get_installation_token(installation_id)

    print(f"  📂 Fetching file tree for {owner}/{repo}...")
    file_list = _fetch_full_tree(token, owner, repo)
    file_paths = [f["path"] for f in file_list]

    print(f"  📄 Found {len(file_paths)} files. Fetching contents in parallel...")

    # Fetch all file contents in parallel
    file_contents = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_path = {
            executor.submit(_fetch_file_content, token, owner, repo, path): path
            for path in file_paths
        }
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                content = future.result()
                if content:
                    file_contents[path] = content
            except Exception as e:
                print(f"  ⚠️  Could not read {path}: {e}")

    tree_visual = _build_tree_visual(file_paths)

    print(f"  ✅ Repo read complete. {len(file_contents)} files loaded.")

    return {
        "owner": owner,
        "repo": repo,
        "file_paths": file_paths,           # flat list of all paths
        "file_contents": file_contents,     # { "path": "content" }
        "tree_visual": tree_visual,         # pretty printed tree
        "total_files": len(file_contents),
    }
