# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is LynX

A Django GitHub App that automatically analyzes repositories on push events. It reads repo contents via the GitHub API, extracts deterministic stack info, generates AI-powered explanations using Groq (Mixtral/Llama models), produces CI/CD GitHub Actions YAML, and stores encrypted results locally. No database ORM usage — just webhook handling and background processing.

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run dev server
python manage.py runserver

# Start webhook proxy (forwards GitHub webhooks to local server via smee.io)
python manage.py lynx webhook

# Production
gunicorn lynx.wsgi:application --bind 0.0.0.0:8000

# CLI management tool
python manage.py lynx installations          # List GitHub App installations
python manage.py lynx repos <install_id>     # List repos for an installation
python manage.py lynx run <owner/repo>       # Run full analysis pipeline (foreground)
python manage.py lynx context <owner/repo>   # Inspect stored encrypted context
python manage.py lynx prefs <install_id>     # View aggregated user preferences
python manage.py lynx webhook                # Start smee webhook proxy for local dev
```

No test suite exists yet.

## Architecture

### Webhook Pipeline (sequential, runs in background threads)

```
POST /agent/webhook/  →  views.py (event routing)
                              ↓
                         tasks.py (ThreadPoolExecutor, 3 workers)
                              ↓
                         pipeline.py (orchestrator)
                              ↓
         Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
       repo_reader  repo_understander  yaml_generator  pr_creator
      (GitHub API)  (Groq narrative)   (Groq CI/CD)   (branch+commit+PR)
                                            ↓
                              pr_description (Groq PR body)
                              ↓
                    context_store.py (Fernet-encrypted storage)
                    .lynx_data/users/<install_id>/repos/<owner>__<repo>/
```

### Context Flow

Context is built once in Phase 1 (`read_repo`) and sliced for downstream phases:

1. **`repo_context["structured"]`** — Deterministic `{stack, has_docker, has_tests, has_lint, has_existing_ci, build_command, test_command}` extracted from file names and contents (no LLM). Injected into both AI phases as a reliable anchor so the LLM cannot hallucinate the stack.
2. **`repo_context["file_contents"]`** — Full file contents. The understander truncates per-file dynamically (`20000 / num_files` chars). The YAML generator only extracts CI-relevant files (package.json, Dockerfile, etc.) capped at 6KB total.
3. **`repo_context["tree_visual"]`** — Visual tree string, shared unchanged across all phases.

Priority files for stack detection are defined in `repo_reader.PRIORITY_FILES`.

### Key Design Patterns

- **Structured context + LLM**: Deterministic stack detection in `repo_reader.extract_structured_context()` feeds into both AI prompts. The LLM enriches this but cannot override the detected stack.
- **Model fallback chain**: Each AI phase tries multiple Groq models in sequence. Understander: qwen3-32b → llama-3.3-70b → llama-4-scout → llama-3.1-8b. YAML generator: llama-3.3-70b → llama-4-scout → qwen3-32b (different priority for code generation).
- **Prompt templates**: Loaded from `agent/prompts/<phase>/system.txt` and `user.txt` at runtime via `agent/prompts/__init__.py`.
- **Encrypted local storage**: All repo contexts encrypted with Fernet (key derived from Django SECRET_KEY via PBKDF2). Metadata files are plaintext JSON and include structured fields (stack, has_docker, etc.) for quick lookup.
- **Background processing**: Webhook returns 202 immediately; analysis runs in ThreadPoolExecutor threads (no Celery).
- **Rate limiting**: Manual `time.sleep()` pauses between Groq API calls (3s between phases, 5s between repos in batch).
- **Webhook proxy**: `python manage.py lynx webhook` runs smee-client to forward GitHub webhooks to local server. Configured via `SMEE_URL` in `.env`.

### URL Routes

- `GET /` — Health check
- `GET /agent/` — Agent home
- `POST /agent/webhook/` — GitHub webhook endpoint (CSRF exempt)

### Webhook Events Handled

- `push` (main/master only) → full pipeline analysis
- `installation` → batch analyze all repos
- `installation_repositories` → analyze added, delete removed
- `pull_request` → logged only (not yet actioned)

### Storage Layout

```
.lynx_data/users/<install_id>/repos/<owner>__<repo>/
  ├── context.enc    # Encrypted full analysis (includes structured context)
  ├── metadata.json  # Status, timestamps, stack, has_docker, has_tests
  ├── ci.yml         # Generated CI workflow
  ├── cd.yml         # Generated CD workflow
  └── report.txt     # Human-readable narrative
```

## Implementation Status

Phases 1-4 (read → understand → generate YAML → create PR) are complete. Full end-to-end: push to repo → PR appears with CI/CD files.

### Phase 4: PR Creation — DONE
- `pr_creator.py`: Creates branch `cicd-agent/setup-pipeline`, commits `ci.yml` + `cd.yml` to `.github/workflows/` via Git Data API (blobs → tree → commit → ref), opens PR. Reuses existing PRs on re-analysis.
- `pr_description.py`: Groq generates a markdown PR body explaining each pipeline section. Falls back to static description.
- Prompts in `agent/prompts/pr_description/`. Wired into `pipeline.py` as Step 4.
- **Requires**: GitHub App Contents permission set to **read & write** (not just read).

### Phase 5: PR Comment Chat (Hours 11-12, stretch) — NOT STARTED
Needs: `issue_comment` webhook handler in `views.py`, feed comment + current YAML + repo context back to Groq, push updated commit to the PR branch.

### Missing Security
- No webhook signature verification (`X-Hub-Signature-256`) in `views.py`
- `.env` and PEM file are committed to git with real credentials

### Missing Testing
No test suite exists. No `tests/` directory, no pytest config.

## Environment Variables

Required in `.env` (loaded via python-dotenv):
- `GITHUB_APP_ID` — GitHub App ID
- `PRIVATE_KEY_PATH` — Path to GitHub App PEM file
- `GROQ_API_KEY` — Groq API key
- `SECRET_KEY` — Django secret (also used for Fernet encryption key derivation)
- `SMEE_URL` — Smee.io channel URL for local webhook forwarding
- `PORT`, `DEBUG`, `ALLOWED_HOSTS` — Standard Django config
