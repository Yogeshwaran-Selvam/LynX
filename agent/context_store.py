"""
Per-repo isolated context storage with encryption.

Directory layout:
    .lynx_data/
      users/
        <installation_id>/
          preferences.enc          # encrypted user-level shared patterns
          repos/
            <owner>__<repo>/
              context.enc          # encrypted full repo analysis
              metadata.json        # plaintext: status, timestamps, stack
"""

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from .context_encryption import encrypt_json, decrypt_json


# Lock per installation_id for safe preference writes
_pref_locks: dict[int, threading.Lock] = {}
_pref_locks_guard = threading.Lock()


def _pref_lock(installation_id: int) -> threading.Lock:
    with _pref_locks_guard:
        if installation_id not in _pref_locks:
            _pref_locks[installation_id] = threading.Lock()
        return _pref_locks[installation_id]


def _data_dir() -> Path:
    return Path(settings.LYNX_DATA_DIR)


def _repo_dir(installation_id: int, owner: str, repo: str) -> Path:
    slug = f"{owner}__{repo}"
    return _data_dir() / "users" / str(installation_id) / "repos" / slug


def _user_dir(installation_id: int) -> Path:
    return _data_dir() / "users" / str(installation_id)


def _atomic_write(path: Path, data: bytes | str):
    """Write to a temp file then rename — prevents corruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(tmp, mode) as f:
        f.write(data)
    os.replace(tmp, path)


# ── Repo context (encrypted) ─────────────────────────────────

def write_repo_context(installation_id: int, owner: str, repo: str, data: dict):
    path = _repo_dir(installation_id, owner, repo) / "context.enc"
    _atomic_write(path, encrypt_json(data))


def read_repo_context(installation_id: int, owner: str, repo: str) -> dict | None:
    path = _repo_dir(installation_id, owner, repo) / "context.enc"
    if not path.exists():
        return None
    return decrypt_json(path.read_bytes())


# ── Metadata (plaintext — non-sensitive operational data) ─────

def write_metadata(installation_id: int, owner: str, repo: str, data: dict):
    path = _repo_dir(installation_id, owner, repo) / "metadata.json"
    # Merge with existing metadata
    existing = read_metadata(installation_id, owner, repo) or {}
    existing.update(data)
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write(path, json.dumps(existing, indent=2))


def read_metadata(installation_id: int, owner: str, repo: str) -> dict | None:
    path = _repo_dir(installation_id, owner, repo) / "metadata.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


# ── User preferences (encrypted, shared across repos) ────────

def write_user_preferences(installation_id: int, prefs: dict):
    path = _user_dir(installation_id) / "preferences.enc"
    with _pref_lock(installation_id):
        _atomic_write(path, encrypt_json(prefs))


def read_user_preferences(installation_id: int) -> dict | None:
    path = _user_dir(installation_id) / "preferences.enc"
    if not path.exists():
        return None
    with _pref_lock(installation_id):
        return decrypt_json(path.read_bytes())


# ── Save output files (plaintext YAML + report) ──────────────

def save_yaml_files(installation_id: int, owner: str, repo: str, yaml_output: dict):
    """Save ci.yml and cd.yml as actual files."""
    repo_path = _repo_dir(installation_id, owner, repo)
    if yaml_output.get("ci"):
        _atomic_write(repo_path / "ci.yml", yaml_output["ci"])
    if yaml_output.get("cd"):
        _atomic_write(repo_path / "cd.yml", yaml_output["cd"])


def save_narrative_report(installation_id: int, owner: str, repo: str,
                          understanding: dict, tree_visual: str):
    """Save the full narrative as a readable report file."""
    repo_path = _repo_dir(installation_id, owner, repo)
    full_name = f"{owner}/{repo}"

    lines = [
        f"LYNX ANALYSIS REPORT: {full_name}",
        "=" * 60,
        "",
        "CORE IDEA:",
        understanding.get("core_idea", "N/A"),
        "",
        "THE FLOW:",
        understanding.get("the_flow", "N/A"),
        "",
        "PROJECT STRUCTURE:",
        tree_visual,
        "",
        f"FILE-BY-FILE NARRATIVE ({len(understanding.get('file_narratives', {}))} files):",
        "-" * 40,
    ]

    for path, bullets in understanding.get("file_narratives", {}).items():
        lines.append(f"\n  {path}")
        if isinstance(bullets, list):
            for bullet in bullets:
                lines.append(f"    - {bullet}")
        else:
            lines.append(f"    - {bullets}")

    key_chars = understanding.get("key_characters", [])
    if key_chars:
        lines.append(f"\nKEY FILES: {', '.join(key_chars)}")

    hidden = understanding.get("hidden_details")
    if hidden:
        lines.append(f"\nHIDDEN DETAIL: {hidden}")

    _atomic_write(repo_path / "report.txt", "\n".join(lines))


# ── Cleanup ───────────────────────────────────────────────────

def delete_repo_context(installation_id: int, owner: str, repo: str):
    repo_path = _repo_dir(installation_id, owner, repo)
    if repo_path.exists():
        shutil.rmtree(repo_path)


# ── Inspection ────────────────────────────────────────────────

def list_repos(installation_id: int) -> list[str]:
    repos_dir = _user_dir(installation_id) / "repos"
    if not repos_dir.exists():
        return []
    return [
        d.name.replace("__", "/")
        for d in repos_dir.iterdir()
        if d.is_dir()
    ]
