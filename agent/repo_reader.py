import logging
import os
import base64
import time
import jwt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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

# Priority files for stack detection (read first, always sent in full)
PRIORITY_FILES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "go.mod", "Cargo.toml", "Gemfile", "composer.json", "pom.xml", "build.gradle",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "tsconfig.json", ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".flake8",
    "jest.config.js", "jest.config.ts", "pytest.ini", "tox.ini", "vitest.config.ts",
    ".github/workflows/ci.yml", ".github/workflows/cd.yml",
}


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
    logger.debug(f"Fetching full file tree for {owner}/{repo}")
    file_list = _fetch_full_tree(token, owner, repo)
    file_paths = [f["path"] for f in file_list]
    logger.debug(f"Found {len(file_paths)} readable files")

    # 2. Fetch all file contents in parallel
    logger.debug("Reading all source files")
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
                logger.warning(f"Could not read {path}: {e}")

    # 3. Build visual tree
    tree_visual = _build_tree_visual(file_paths)

    # 4. Extract deterministic structured context
    structured = extract_structured_context(file_paths, file_contents)
    logger.info(f"Structured context: stack={structured['stack']}, "
                f"docker={structured['has_docker']}, tests={structured['has_tests']}")

    logger.debug(f"Repo read complete. {len(file_contents)} files loaded.")

    return {
        "owner": owner,
        "repo": repo,
        "file_paths": file_paths,
        "file_contents": file_contents,
        "tree_visual": tree_visual,
        "total_files": len(file_contents),
        "structured": structured,
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


def extract_structured_context(file_paths: list[str], file_contents: dict) -> dict:
    """
    Deterministic stack detection from file names and contents.
    Produces a compact context object independent of any LLM call.
    """
    names = {p.split("/")[-1] for p in file_paths}
    paths_set = set(file_paths)

    # Stack detection
    stack = "unknown"
    if "package.json" in names:
        stack = "node"
    elif "requirements.txt" in names or "pyproject.toml" in names or "setup.py" in names:
        stack = "python"
    elif "go.mod" in names:
        stack = "go"
    elif "Cargo.toml" in names:
        stack = "rust"
    elif "pom.xml" in names or "build.gradle" in names:
        stack = "java"
    elif "Gemfile" in names:
        stack = "ruby"
    elif "composer.json" in names:
        stack = "php"

    # Docker
    has_docker = "Dockerfile" in names or "docker-compose.yml" in names or "docker-compose.yaml" in names

    # Tests
    has_tests = any(
        "test" in p.lower() or "spec" in p.lower() or "__tests__" in p
        for p in file_paths
    )

    # Lint config (include tslint)
    lint_config = names & {
        ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
        "tslint.json",
        ".flake8", ".pylintrc", "pylintrc", ".golangci.yml",
        "biome.json", ".prettierrc",
    }
    has_lint = bool(lint_config)
    lint_tool = None
    if "tslint.json" in lint_config:
        lint_tool = "tslint"
    elif lint_config & {".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml"}:
        lint_tool = "eslint"
    elif lint_config & {".flake8", ".pylintrc", "pylintrc"}:
        lint_tool = "flake8"
    elif ".golangci.yml" in lint_config:
        lint_tool = "golangci-lint"

    # Existing CI
    has_existing_ci = any(p.startswith(".github/workflows/") for p in file_paths)

    # Lock file detection (determines npm ci vs npm install)
    has_lock_file = bool(names & {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum",
        "Gemfile.lock", "composer.lock",
    })

    # Build & test commands from config files
    build_command = None
    test_command = None
    install_command = None
    project_name = None

    pkg = file_contents.get("package.json")
    if pkg:
        try:
            import json
            pkg_data = json.loads(pkg)
            project_name = pkg_data.get("name")
            scripts = pkg_data.get("scripts", {})
            install_command = "npm ci" if has_lock_file else "npm install"
            if "build" in scripts:
                build_command = "npm run build"
            if "test" in scripts:
                test_command = "npm test"
            if not has_lint and ("lint" in scripts):
                has_lint = True
                lint_tool = "eslint"
        except (json.JSONDecodeError, TypeError):
            pass

    pyproject = file_contents.get("pyproject.toml")
    if pyproject and stack == "python":
        if "pytest" in pyproject:
            test_command = "pytest"
        if "[project]" in pyproject:
            for line in pyproject.splitlines():
                if line.strip().startswith("name"):
                    project_name = line.split("=", 1)[-1].strip().strip('"').strip("'")
                    break

    if stack == "python" and not test_command:
        if "pytest.ini" in names or "tox.ini" in names:
            test_command = "pytest"

    if stack == "go":
        build_command = "go build ./..."
        test_command = "go test ./..."

    if stack == "rust":
        build_command = "cargo build"
        test_command = "cargo test"

    return {
        "stack": stack,
        "project_name": project_name,
        "has_docker": has_docker,
        "has_tests": has_tests,
        "has_lint": has_lint,
        "lint_tool": lint_tool,
        "has_lock_file": has_lock_file,
        "has_existing_ci": has_existing_ci,
        "install_command": install_command,
        "build_command": build_command,
        "test_command": test_command,
        "total_files": len(file_paths),
    }
