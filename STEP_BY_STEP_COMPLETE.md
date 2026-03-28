# 🎯 LynX - Complete Step-by-Step Execution Guide (Unified)

> **Total Time: ~15 minutes from start to first working push**

---

## 📋 STEP 1: Prepare Virtual Environment ⏱️ 2 mins

### 1.1 Open PowerShell in Project Directory
```powershell
cd 'c:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX'
```

### 1.2 Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

**Expected**: Prompt should show `(venv)` prefix:
```
(venv) PS C:\Users\...\LynX>
```

### 1.3 Verify Python & Dependencies
```powershell
python --version
pip list | Select-String -Pattern "Django|groq|requests"
```

**Expected Output**:
```
Python 3.12.x
Django            4.2.x
groq              0.x.x
requests          2.x.x
```

---

## 🔑 STEP 2: Get API Credentials ⏱️ 8 mins

### 2.1 Get Groq API Key (2 minutes - FREE!)

1. **Open**: https://console.groq.com/keys
2. **Click**: "Create API Key"
3. **Name it**: `LynX` (or any name)
4. **Copy the key** (starts with `gsk_`)
5. **Keep it safe** - you'll need it next

### 2.2 Create GitHub App (4 minutes)

1. **Open**: https://github.com/settings/apps
2. **Click**: "New GitHub App"
3. **Fill Form**:
   - **App name**: `LynX` (or your choice)
   - **Homepage URL**: `http://localhost:8000`
   - **Webhook URL**: `http://localhost:8000/agent/webhook/` (change later)
   - **Webhook active**: ✅ Checked
   - **Repository permissions**: 
     - "Contents": Read-only
   - **Subscribe to events**: ✅ Push
   - **Where can this app be installed**: "Any account"

4. **Click**: "Create GitHub App"

### 2.3 Download GitHub App Private Key (2 minutes)

1. On your app settings page, scroll down
2. Click: "Generate a private key"
3. A `.pem` file downloads
4. **Move it** to: `c:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX\private-key.pem`

### 2.4 Get Your App ID

On the same GitHub App settings page, find:
- **App ID**: `1234567` (example)
- Copy this number for next step

### 2.5 Generate Webhook Secret

In PowerShell, run:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output (it's a random string)

---

## ⚙️ STEP 3: Configure .env File ⏱️ 2 mins

### 3.1 Edit `.env` File

**Open**: `c:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX\.env`

**Replace** `your_*` values with your actual credentials:

```env
# GitHub App
GITHUB_APP_ID=1234567
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=your_random_webhook_secret_here

# Groq AI
GROQ_API_KEY=gsk_your_groq_key_here

# Django
DEBUG=True
SECRET_KEY=your-django-secret-key-change-this
ALLOWED_HOSTS=localhost,127.0.0.1
PORT=8000
```

**Example Filled In**:
```env
GITHUB_APP_ID=987654
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=V7xY9pQrT2kL8nM3wJ5bX1vS4dF6gH9j
GROQ_API_KEY=gsk_2Jk8L9mN0pQ1rS2tU3vW4xY5zAbC6dEf
DEBUG=True
SECRET_KEY=lynx-dev-secret-key-123456789
ALLOWED_HOSTS=localhost,127.0.0.1
PORT=8000
```

### 3.2 Verify Files Are in Place

In PowerShell:
```powershell
ls -Name *.pem, *.env
```

**Expected**:
```
.env
private-key.pem
```

---

## 🚀 STEP 4: Run Django Server ⏱️ 1 min

### 4.1 Start Django

In PowerShell (with venv activated):
```powershell
python manage.py runserver
```

**Expected Output**:
```
Django version 4.2.x
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### 4.2 Keep This Window Open!

Don't close this terminal - LynX runs here and outputs analysis logs.

---

## 🌐 STEP 5: Setup ngrok Tunnel (for Testing) ⏱️ 3 mins

### 5.1 Download ngrok (First Time Only)

1. Go to: https://ngrok.com/download
2. Download for Windows
3. Extract the exe file

### 5.2 Open NEW PowerShell Window

**Don't close** the one with Django running!

```powershell
# Navigate to ngrok
cd 'C:\path\to\ngrok'  # or add ngrok to PATH

# Start tunnel
ngrok http 8000
```

**Expected Output**:
```
Session Status                online
Forwarding                    https://abc123def456.ngrok.io -> http://localhost:8000
```

**Copy this URL**: `https://abc123def456.ngrok.io`

### 5.3 Keep This Window Open Too!

ngrok needs to keep running.

---

## 🔗 STEP 6: Update GitHub Webhook URL ⏱️ 2 mins

### 6.1 Update in GitHub Settings

1. Go to: https://github.com/settings/apps/LynX (your app)
2. Click: **"Webhook"** in left sidebar
3. Change **Webhook URL** to: `https://abc123def456.ngrok.io/agent/webhook/`
4. **Webhook secret**: Paste your webhook secret from `.env`
5. **Click**: "Save changes"

**Format should look like**:
```
Webhook URL:    https://abc123def456.ngrok.io/agent/webhook/
Content type:   application/json
Secret:         V7xY9pQrT2kL8nM3wJ5bX1vS4dF6gH9j
Active:         ✅
Events:         Push
```

---

## 🧪 STEP 7: Create Test Repository ⏱️ 3 mins

### 7.1 Create Repo on GitHub

1. Go to: https://github.com/new
2. **Repository name**: `test-lynx-app`
3. **Description**: `Testing LynX GitHub App`
4. Click: **"Create repository"**

### 7.2 Install LynX App on Test Repo

1. In your test repo, go to: **Settings**
2. Go to: **Integrations & services**
3. Find: **"GitHub Apps"** section
4. Search for: `LynX`
5. Click: **"Install"**
6. Select your test repo
7. Click: **"Install"** again

---

## 🔄 STEP 8: Trigger the Webhook ⏱️ 2 mins

### 8.1 Clone & Push Code

Open a **3rd PowerShell window** (keep the other 2 running!):

```powershell
# Clone your test repo
git clone https://github.com/YOUR_USERNAME/test-lynx-app.git test-repo
cd test-repo

# Create test files
echo "# My Test Repo" | Out-File -Encoding utf8 README.md
echo '{"name": "test"}' | Out-File -Encoding utf8 package.json
echo "Django>=4.2" | Out-File -Encoding utf8 requirements.txt

# Add and commit
git add .
git commit -m "Initial commit - testing LynX"
git push origin main
```

### 8.2 Watch the Magic in Django Terminal! 👀

**Look at STEP 4's terminal** (where Django is running).

You should see:

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
  ✅ Core idea: A test repository for demonstrating...

🧠 Understanding:
{
  "core_idea": "A test repository for validating LynX GitHub App integration with Groq AI",
  "stack": "Mixed (Node.js + Python)",
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
    "README.md": "Main project documentation",
    "package.json": "Node.js project configuration",
    "requirements.txt": "Python dependencies specification"
  },
  "key_entry_points": [],
  "deployment_hints": "Mixed technology repository without clear deployment patterns"
}
```

✅ **SUCCESS! LynX just analyzed your repo!**

---

## 🎉 STEP 9: Verify Everything Worked ⏱️ 1 min

### Checklist:

- ✅ Virtual environment created and activated
- ✅ Dependencies installed (`Django`, `groq`, `requests`, etc.)
- ✅ `.env` file configured with credentials
- ✅ `private-key.pem` in root folder
- ✅ GitHub App created
- ✅ ngrok tunnel running
- ✅ GitHub webhook URL updated
- ✅ Django server running
- ✅ Test repo created
- ✅ LynX app installed on test repo
- ✅ Push triggered webhook
- ✅ LynX analyzed repository with Groq
- ✅ JSON analysis output in Django logs

### If All Checked ✅:
**Congratulations! LynX is working perfectly!**

---

## 🔧 Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Activate venv: `.\venv\Scripts\Activate.ps1` |
| `Can't find .pem file` | Download from GitHub App settings, save as `./private-key.pem` |
| `GROQ_API_KEY error` | Check `.env` has the key, no extra spaces |
| `Webhook not triggering` | Check ngrok URL is correct in GitHub, app installed on repo |
| Django server won't start | Check port 8000 isn't in use: `netstat -ano \| findstr :8000` |
| Groq API fails | Check quota at https://console.groq.com, free tier has limits |
| No output in terminal | Look at the right window - Django server window, not ngrok |

---

## 🚀 NEXT STEPS (Optional Advanced)

### Deploy to Production:
1. Set `DEBUG=False` in `.env`
2. Update `ALLOWED_HOSTS` with your domain
3. Use permanent domain instead of ngrok
4. Deploy with Gunicorn/Docker
5. Update all webhook URLs

### Implement Phases 3-4:
1. Modify `repo_understander.py` output format
2. Create YAML generator from analysis
3. Implement PR creation workflow
4. Add support for multiple CI platforms

### Test with Real Repos:
1. Install LynX on your own projects
2. See analysis for different project types
3. Customize prompts and analysis
4. Build dashboard for viewing analyses

---

## 📚 Files You Have

| File | Purpose |
|------|---------|
| `README.md` | Project overview |
| `QUICK_START.md` | 5-minute reference |
| `EXECUTION_GUIDE.md` | Detailed multi-phase guide |
| `IMPLEMENTATION_SUMMARY.md` | Technical implementation details |
| `STEP_BY_STEP_COMPLETE.md` | **This file** - Unified steps |

---

## ✅ Success Indicators

### When you see this in Django logs:
```
🚀 Push on user/repo — starting LynX agent
  ✅ Repo read complete
  🤖 Calling Groq to understand repository...
  ✅ Core idea: ...
🧠 Understanding: {...}
```

### You know:
- ✅ GitHub webhook is working
- ✅ Django is receiving events
- ✅ Repository reading is working
- ✅ Groq API is connected
- ✅ Analysis pipeline is complete

---

## 🎓 Learning Tips

- **Understand Flow**: Read `repo_reader.py` → `repo_understander.py` → `views.py`
- **Experiment**: Try modifying prompts in `repo_understander.py`
- **Test**: Create different types of repos (Node.js, Go, Python, etc.)
- **Monitor**: Check Groq usage at https://console.groq.com
- **Scale**: Once working, deploy to production

---

## 🕐 Time Summary

| Step | Time |
|------|------|
| 1. Virtual Environment | 2 mins |
| 2. Get Credentials | 8 mins |
| 3. Configure .env | 2 mins |
| 4. Run Django | 1 min |
| 5. Setup ngrok | 3 mins |
| 6. Update Webhook | 2 mins |
| 7. Create Test Repo | 3 mins |
| 8. Trigger & Watch | 2 mins |
| **TOTAL** | **~23 mins** |

---

## 🐾 You're Ready!

Start with **STEP 1** above and follow through.

If you get stuck, check the troubleshooting table or refer to other documentation files.

**Happy LynX-ing! 🚀**
