# 🚀 LynX Complete Execution Guide (Step-by-Step)

## ✅ Now Using Groq API Instead of Anthropic!

---

# PHASE 1: LOCAL SETUP (Completed ✅)

## Step 1.1 - Navigate to Project Directory
```powershell
cd 'c:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX'
Get-Location  # Verify current directory
```

**Expected Output:**
```
Path
----
C:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX
```

## Step 1.2 - Verify Python & Create Virtual Environment
```powershell
python --version  # Should show Python 3.10+
python -m venv venv
```

**Expected Output:**
```
Python 3.12.x
(venv folder created)
```

## Step 1.3 - Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

**Expected Output:**
```
(venv) PS C:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX>
```

## Step 1.4 - Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected Output:**
```
Successfully installed Django requests PyJWT cryptography groq python-dotenv gunicorn
```

## Step 1.5 - Verify All Imports
```powershell
python -c "import django; import requests; import groq; import jwt; print('✅ All imports work!')"
```

**Expected Output:**
```
✅ All imports work!
```

---

# PHASE 2: GET CREDENTIALS (NEW - Groq API)

## Step 2.1 - Get Groq API Key (FREE!)

1. Go to: **https://console.groq.com/keys**
2. Click **"Create API Key"**
3. Name it: `LynX`
4. Copy the key (keep it safe!)
5. Paste it into your `.env` file:

```env
GROQ_API_KEY=gsk_your_actual_key_here
```

## Step 2.2 - Create GitHub App

1. Go to: **https://github.com/settings/apps**
2. Click **"New GitHub App"**
3. Fill in:
   - **App name**: `LynX`
   - **Homepage URL**: `http://localhost:8000`
   - **Webhook URL**: (leave blank for now)
   - **Webhook active**: ✅ Checked
   - **Repository permissions**: `Contents: Read-only`
   - **Events**: `Push`
   - **Where can this app be installed**: "Any account"
4. Click **"Create GitHub App"**

## Step 2.3 - Get GitHub App Credentials

1. On your app page, copy:
   - **App ID** → Paste into `.env` as `GITHUB_APP_ID`
   - **Private Key**: Click "Generate Private Key" and download
2. Place the downloaded `.pem` file in your LynX root folder: `./private-key.pem`
3. Generate a **Webhook Secret**:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
4. Paste the output into `.env` as `WEBHOOK_SECRET`

## Step 2.4 - Final .env File

Your `.env` should look like:

```env
GITHUB_APP_ID=1234567
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=your_random_webhook_secret
GROQ_API_KEY=gsk_your_groq_key_here
PORT=8000
DEBUG=True
SECRET_KEY=django-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

# PHASE 3: RUN LYNX LOCALLY

## Step 3.1 - Start Django Server

```powershell
# Make sure (venv) is active
python manage.py runserver
```

**Expected Output:**
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

## Step 3.2 - Verify Server is Running

In a **new PowerShell window**, run:

```powershell
curl http://localhost:8000/agent/webhook/
```

You should get a **404 or error** (expected - webhook only accepts POST on push events)

---

# PHASE 4: TEST WITH NGROK (Local Testing)

## Step 4.1 - Download & Install ngrok

1. Go to: **https://ngrok.com/download**
2. Download for Windows
3. Extract and note the path
4. Add to PATH or run from extraction folder

## Step 4.2 - Start ngrok Tunnel

```powershell
ngrok http 8000
```

**Expected Output:**
```
Session Status                online
Account                       Free
Version                       3.x.x
Region                        Singapore
Forwarding                    https://abc123.ngrok.io -> http://localhost:8000
Connections                   0/40 active
```

**Copy the ngrok URL**: `https://abc123.ngrok.io`

## Step 4.3 - Update GitHub App Webhook

1. Go to: **https://github.com/settings/apps/LynX**
2. Click **"Webhook"**
3. Set:
   - **Webhook URL**: `https://abc123.ngrok.io/agent/webhook/`
   - **Content type**: `application/json`
   - **Secret**: Copy from your `.env` WEBHOOK_SECRET
   - **Active**: ✅ Checked
   - **Events**: `Push`
4. Click **"Save changes"**

---

# PHASE 5: CREATE TEST REPO & TRIGGER WEBHOOK

## Step 5.1 - Create Test Repository on GitHub

1. Go to: **https://github.com/new**
2. Name: `test-lynx-app`
3. Description: `Test repository for LynX`
4. Public or Private (doesn't matter)
5. Click **"Create repository"**

## Step 5.2 - Install GitHub App on Test Repo

1. Go to your test repo
2. Settings → **Integrations & services**
3. Click **"GitHub Apps"** → Search for "LynX"
4. Click **"Install"** → Select your test repo → **Install**

## Step 5.3 - Push Code to Trigger Webhook

```powershell
# In a new folder
git clone https://github.com/YOUR_USERNAME/test-lynx-app.git test-repo
cd test-repo

# Create some files
echo "# Test Repo" | Out-File -Encoding utf8 README.md
echo "package.json" | Out-File -Encoding utf8 package.json
echo "requirements.txt" | Out-File -Encoding utf8 requirements.txt

# Commit and push
git add .
git commit -m "Initial commit to test LynX"
git push origin main
```

## Step 5.4 - Watch the Magic! 🎉

In your **LynX Terminal** (where `python manage.py runserver` is running), watch for:

```
🚀 Push on YOUR_USERNAME/test-lynx-app — starting LynX agent

  📂 Fetching file tree for YOUR_USERNAME/test-lynx-app...
  📄 Found 3 files. Fetching contents in parallel...
  ✅ Repo read complete. 3 files loaded.

📁 File Tree:
├── README.md
├── package.json
└── requirements.txt

  🤖 Calling Groq to understand repository...
  ✅ Core idea: A test repository for validating LynX...

🧠 Understanding:
{
  "core_idea": "A test repository for validating LynX GitHub App integration",
  "stack": "Multi-stack",
  "project_type": "other",
  "has_tests": false,
  "has_docker": false,
  "has_existing_ci": false,
  "build_commands": {
    "install": null,
    "build": null,
    "test": null,
    "lint": null
  },
  "file_explanations": {
    "README.md": "Main documentation file providing project overview",
    "package.json": "Node.js project configuration",
    "requirements.txt": "Python dependencies configuration"
  },
  "key_entry_points": [],
  "deployment_hints": "Mixed technology repository without clear deployment patterns"
}
```

✅ **SUCCESS! LynX just analyzed your repo with Groq API!**

---

# PHASE 6: VERIFY EVERYTHING

## Checklist

- ✅ Virtual environment created & activated
- ✅ All dependencies installed (Django, Groq, etc.)
- ✅ GitHub App created & configured
- ✅ `.env` file with all credentials
- ✅ `private-key.pem` placed in root folder
- ✅ ngrok running with tunnel
- ✅ GitHub App webhook URL updated
- ✅ Test repo created & app installed
- ✅ Push triggered webhook
- ✅ LynX logged repo analysis
- ✅ Groq API returned JSON analysis

---

# PHASE 7: DEPLOY TO PRODUCTION (Optional)

## Production Deployment with Gunicorn

```powershell
# Ensure (venv) is active
gunicorn lynx.wsgi:application --bind 0.0.0.0:8000
```

### Deploy to Heroku:

```powershell
# Install Heroku CLI
# heroku login
# heroku create lynx-app
# git push heroku main
```

### Deploy to AWS/DigitalOcean:

1. Set `DEBUG=False` in `.env`
2. Update `ALLOWED_HOSTS` with your domain
3. Install systemd service or Docker container
4. Update GitHub webhook URL to production domain
5. Use `gunicorn` with proper WSGI server

---

# Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Activate venv: `.\venv\Scripts\Activate.ps1` |
| `GROQ_API_KEY not found` | Check .env has correct format |
| `private-key.pem not found` | Download from GitHub App settings |
| Webhook not triggering | Check ngrok URL is correct, app installed on repo |
| `Connection refused` | Django server not running on `localhost:8000` |
| Groq API error | Check quota at https://console.groq.com/keys |
| No output in terminal | Check you're looking at LynX server terminal, not ngrok |

---

# Files Modified for Groq Integration

1. **requirements.txt**: Changed `anthropic` → `groq`
2. **.env**: Changed `ANTHROPIC_API_KEY` → `GROQ_API_KEY`
3. **agent/repo_understander.py**: 
   - Import: `anthropic` → `from groq import Groq`
   - Model: `claude-sonnet-4` → `mixtral-8x7b-32768`
   - API format: Updated to Groq's chat completions format

---

# Next Steps

1. **Test with your own repos** - Install app on any GitHub repo
2. **Customize analysis** - Modify prompts in `repo_understander.py`
3. **Implement Phase 4** - Generate GitHub Actions YAML from understanding
4. **Create auto-PR** - Submit generated workflows as PRs
5. **Add more models** - Use other Groq models (Llama, etc.)

---

**Happy LynX-ing! 🐾**
