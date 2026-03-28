# LynX 🐾

A GitHub App that intelligently analyzes any target repository and generates actionable project intelligence.

## Overview

LynX is a Django-based intelligent repository analysis engine that:

1. **Reads** the entire repository structure recursively
2. **Fetches** individual file contents in parallel
3. **Understands** the project's core idea and tech stack using Claude AI
4. **Generates** per-file explanations and deployment hints
5. **Prepares** context for downstream YAML-based CI/CD generation

When LynX is installed on a repository, it triggers on every push to `main`/`master` and provides deep repository intelligence.

## Project Structure

```
LynX/
├── manage.py                    ← Django CLI
├── .env                         ← Environment variables
├── private-key.pem              ← GitHub App private key
├── requirements.txt             ← Python dependencies
├── lynx/                        ← Django project
│   ├── __init__.py
│   ├── settings.py              ← Django configuration
│   ├── urls.py                  ← URL routing
│   └── wsgi.py                  ← WSGI application
└── agent/                       ← Main app
    ├── __init__.py
    ├── apps.py
    ├── urls.py
    ├── views.py                 ← Webhook entry point
    ├── repo_reader.py           ← File tree + content puller
    ├── repo_understander.py     ← Claude-powered analysis
    └── stack_detector.py        ← (Upcoming) Stack detection
```

## Setup

### 1. Install Dependencies

```bash
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` with:

```env
GITHUB_APP_ID=your_app_id
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=your_webhook_secret
ANTHROPIC_API_KEY=your_anthropic_key
DEBUG=True
SECRET_KEY=your-django-secret-key
```

### 3. Add GitHub App Private Key

Place your GitHub App's private key at `./private-key.pem`

### 4. Run the Server

```bash
python manage.py runserver
```

Or with Gunicorn for production:

```bash
gunicorn lynx.wsgi:application --bind 0.0.0.0:8000
```

## How It Works

### Phase 1: Repository Reading (`repo_reader.py`)

- Gets an installation token for the target repo
- Uses GitHub's Git Trees API with `recursive=1` to fetch entire file structure in one call
- Filters out noise (node_modules, .git, binary files, large files > 50KB)
- Fetches individual file contents in parallel using ThreadPoolExecutor
- Builds a visual tree representation

**Output:**
```json
{
  "owner": "username",
  "repo": "repo-name",
  "file_paths": ["src/app.py", "requirements.txt", ...],
  "file_contents": {"src/app.py": "import...", ...},
  "tree_visual": "├── src/\n│   └── app.py\n└── requirements.txt",
  "total_files": 24
}
```

### Phase 2: Repository Understanding (`repo_understander.py`)

- Sends repo data to Claude AI with smart context prioritization
- Priority files (package.json, requirements.txt, Dockerfile, etc.) sent fully
- Other files truncated to first 300 chars
- Claude returns structured analysis:

**Output:**
```json
{
  "core_idea": "A Django REST API for managing user authentication and authorization",
  "stack": "Python/Django",
  "project_type": "web-api",
  "has_tests": true,
  "has_docker": true,
  "has_existing_ci": false,
  "build_commands": {
    "install": "pip install -r requirements.txt",
    "build": null,
    "test": "pytest",
    "lint": "flake8"
  },
  "file_explanations": {
    "manage.py": "Django CLI entry point",
    "src/views.py": "Contains API endpoint handlers"
  },
  "key_entry_points": ["manage.py"],
  "deployment_hints": "Dockerizable Django app, likely deployed to Heroku or AWS"
}
```

### Phase 3: Webhook Handler (`views.py`)

- Listens for GitHub push events on main/master
- Orchestrates Phases 1 & 2
- Logs all progress with emojis for visibility
- Ready to trigger downstream YAML generation

## Example Webhook Output

```
🚀 Push on some-user/some-repo — starting LynX agent

  📂 Fetching file tree for some-user/some-repo...
  📄 Found 24 files. Fetching contents in parallel...
  ✅ Repo read complete. 24 files loaded.

📁 File Tree:
├── Dockerfile
├── requirements.txt
├── manage.py
└── src/
    ├── views.py
    ├── models.py
    └── urls.py

  🤖 Calling Claude to understand repository...
  ✅ Core idea: A Django REST API for managing user auth...

🧠 Understanding:
{
  "core_idea": "A Django REST API for managing user authentication...",
  "stack": "Python/Django",
  "has_tests": true,
  "has_docker": true,
  "file_explanations": {
    "manage.py": "Django's CLI entry point for running the server and migrations",
    "src/views.py": "Contains API endpoint handlers for user registration and login",
    ...
  }
}
```

## GitHub App Configuration

### Webhook Events

Subscribe to:
- `push` - Triggers on every push to main/master

### Webhook URL

Set to: `https://your-domain.com/agent/webhook/`

### Permissions

- **Repository**: `contents:read`
- **Repository**: `pull_requests:write` (for Phase 4: YAML generation)

## Next Steps (Phase 3-4)

- [ ] Implement stack detection (Go, Node.js, Python, Ruby, etc.)
- [ ] Generate GitHub Actions YAML based on project type
- [ ] Create PR with generated CI/CD workflows
- [ ] Add support for multiple CI platforms (GitHub Actions, GitLab CI, CircleCI)

## Dependencies

- **Django**: Web framework
- **requests**: HTTP client for GitHub API
- **PyJWT + cryptography**: JWT token signing
- **anthropic**: Claude API client
- **python-dotenv**: Environment variable management
- **gunicorn**: Production WSGI server

## License

MIT
