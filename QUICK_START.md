# 🚀 QUICK START - LynX with Groq API

## ⚡ 5-Minute Quick Reference

### Step 1: Activate Virtual Environment
```powershell
cd 'c:\Users\Josephin Yazhini\Downloads\hackthefuture\LynX'
.\venv\Scripts\Activate.ps1
```

### Step 2: Get API Keys (2 minutes)

**Groq API Key (FREE!):**
- Go to: https://console.groq.com/keys
- Create API Key
- Copy & paste into `.env`

**GitHub App:**
- Go to: https://github.com/settings/apps
- Create new GitHub App
- Get App ID & download private key
- Copy to `.env` and save private key as `./private-key.pem`

### Step 3: Update .env File
```env
GITHUB_APP_ID=your_app_id
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=generate_random_string
GROQ_API_KEY=your_groq_key
DEBUG=True
SECRET_KEY=your-secret-key
```

### Step 4: Start LynX
```powershell
python manage.py runserver
```

### Step 5: Setup ngrok (Testing)
```powershell
ngrok http 8000
# Copy ngrok URL and update GitHub webhook URL
```

### Step 6: Create Test Repo & Push
```powershell
git clone https://github.com/YOUR_USERNAME/test-lynx-app.git
cd test-lynx-app
echo "# Test" > test.md
git add .
git commit -m "Trigger webhook"
git push origin main
```

### Step 7: Watch Terminal Output
Should see:
```
🚀 Push on user/repo — starting LynX agent
  📂 Fetching file tree...
  ✅ Repo read complete
  🤖 Calling Groq...
  🧠 Understanding: {JSON analysis}
```

---

## ✅ What Changed (Anthropic → Groq)

| Component | Before | After |
|-----------|--------|-------|
| AI Provider | Claude (Anthropic) | Mixtral (Groq) |
| API Package | `anthropic` | `groq` |
| API Key | `ANTHROPIC_API_KEY` | `GROQ_API_KEY` |
| Cost | Paid | **FREE** ✅ |
| Setup Complexity | Complex | **Simple** ✅ |

---

## 📂 Files Modified

1. ✅ `requirements.txt` - Replaced anthropic with groq
2. ✅ `.env` - Changed API key variable
3. ✅ `agent/repo_understander.py` - Updated API calls & model
4. ✅ `EXECUTION_GUIDE.md` - Complete step-by-step guide

---

## 🎯 Full Timeline

```
Phase 1: Local Setup ..................... ✅ DONE
Phase 2: Get Credentials ................ 📋 NEXT (5 mins)
Phase 3: Run Django Server .............. 📋 NEXT (1 min)
Phase 4: Setup ngrok Tunnel ............. 📋 NEXT (2 mins)
Phase 5: Create Test Repo & Push ........ 📋 NEXT (3 mins)
Phase 6: Watch Analysis ................. 📋 NEXT (1 min)
Phase 7: Deploy to Production ........... 📋 OPTIONAL
```

---

## 📞 Common Commands

```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Start Django server
python manage.py runserver

# Run ngrok tunnel
ngrok http 8000

# Test imports
python -c "import django; import groq; print('OK')"

# Run Django migrations (once)
python manage.py migrate

# Create Django superuser (optional)
python manage.py createsuperuser
```

---

## 🔑 What You Need Right Now

1. ✅ Virtual environment (created)
2. ✅ Dependencies installed (Groq ready)
3. ⏳ **Groq API Key** - Get from https://console.groq.com/keys (1 min)
4. ⏳ **GitHub App ID** - Create at https://github.com/settings/apps (2 mins)
5. ⏳ **GitHub App Private Key** - Download from app settings (1 min)

**→ Total time to ready: ~5 minutes!**

---

## ✅ Ready? Go to EXECUTION_GUIDE.md for detailed steps!

Start with **PHASE 2: GET CREDENTIALS**
