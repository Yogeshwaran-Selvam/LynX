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

# Extensions to skip (binaries, assets, locks)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".rar",
    ".lock", ".min.js", ".min.css", ".map",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".tox", ".eggs", "vendor", ".bundle", "target",
}

MAX_FILE_SIZE = 50_000  # 50KB per file


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


# ── Full recursive tree (single API call) ────────────────────

def _fetch_full_tree(token: str, owner: str, repo: str) -> list[dict]:
    """
    Uses Git Trees API with recursive=1 to get the entire file tree
    in ONE API call. Returns list of {path, size} for readable files.
    """
    # Get default branch SHA
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

    # Recursive tree — one call for everything
    tree_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}",
        headers=_headers(token),
        params={"recursive": "1"},
    )
    tree_resp.raise_for_status()

    files = []
    for item in tree_resp.json().get("tree", []):
        if item["type"] != "blob":
            continue

        path = item["path"]
        size = item.get("size", 0)

        # Skip noise dirs
        parts = path.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue

        # Skip binary/noise extensions
        _, ext = os.path.splitext(path)
        if ext.lower() in SKIP_EXTENSIONS:
            continue

        # Skip large files
        if size > MAX_FILE_SIZE:
            continue

        files.append({"path": path, "size": size})

    return files


# ── Fetch single file content ────────────────────────────────

def _fetch_file_content(token: str, owner: str, repo: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(token))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, list):
        return "\n".join(item["name"] for item in data)

    if data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None
    return None


# ── Main entry point ──────────────────────────────────────────

def read_repo(installation_id: int, owner: str, repo: str) -> dict:
    """
    Deep-reads the repo: fetches full tree, then reads ALL source files
    in parallel. Produces a complete picture for the AI narrator.
    """
    token = _get_installation_token(installation_id)

    # 1. Get full recursive file tree (single API call)
    print(f"  📂 Fetching full file tree for {owner}/{repo}...")
    file_list = _fetch_full_tree(token, owner, repo)
    file_paths = [f["path"] for f in file_list]
    print(f"  📄 Found {len(file_paths)} readable files")

    # 2. Fetch all file contents in parallel
    print(f"  🔍 Reading all source files...")
    file_contents = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_path = {
            executor.submit(_fetch_file_content, token, owner, repo, f["path"]): f["path"]
            for f in file_list
        }
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                content = future.result()
                if content:
                    file_contents[path] = content
            except Exception as e:
                print(f"  ⚠️  Could not read {path}: {e}")

    # 3. Build visual tree
    tree_visual = _build_tree_visual(file_paths)

    print(f"  ✅ Repo read complete. {len(file_contents)} files loaded.")

    return {
        "owner": owner,
        "repo": repo,
        "file_paths": file_paths,
        "file_contents": file_contents,
        "tree_visual": tree_visual,
        "total_files": len(file_contents),
    }


def _build_tree_visual(file_paths: list[str]) -> str:
    """Flat paths → visual tree string."""
    tree = {}
    for path in sorted(file_paths):
        parts = path.split("/")
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    lines = []

    def render(node, prefix=""):
        items = sorted(node.items())
        for i, (key, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{key}")
            if subtree:
                extension = "    " if is_last else "│   "
                render(subtree, prefix + extension)

    render(tree)
    return "\n".join(lines)
