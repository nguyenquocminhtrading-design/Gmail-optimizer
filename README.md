# Gmail Intelligence & Interactive Email Classification System

A production-grade, local-first / server-deployable Gmail automation & email intelligence system built with **FastAPI**, **SQLite**, **OAuth 2.0 Web Flow**, and a **Multi-Layer Hybrid Intelligence Classifier**.

Designed to connect to your Gmail account, parse & normalize email content, extract deadlines and action items, classify emails with confidence scoring, manage dedicated `AI/*` Gmail labels, and provide an interactive web dashboard for user-in-the-loop feedback learning.

---

## Key Features

- 🔐 **OAuth 2.0 Web Authentication**: No stored passwords. Safe, Google-approved web consent flow.
- ⚡ **Multi-Layer Hybrid Classifier**:
  1. **Hard Overrides & User Rules** (e.g., *Never archive emails from Professor X*)
  2. **Multi-Signal Heuristic Rules** (Urgency keywords, deadline proximity, category matching)
  3. **Sender Intelligence** (Historical statistics & response tracking)
  4. **Optional Gemini AI Engine** (Contextual reasoning via `GEMINI_API_KEY`)
- 🤖 **User-in-the-Loop Feedback Learning**:
  - Interactively review low-confidence predictions on the dashboard.
  - Teach the system by choosing rule scopes: **Only this email**, **All emails from this sender**, or **Similar subjects**.
- 🏷️ **Safe Gmail Label Management**:
  - Creates dedicated `AI/` namespace labels (`AI/Urgent`, `AI/Important`, `AI/Action Required`, `AI/Review`, `AI/Career`, `AI/Finance`, etc.).
  - Preserves all original user labels.
- 🛡️ **Safety First**:
  - `DRY_RUN=True` default prevents accidental Gmail label modification until verified.
  - Destructive actions (deletion, sending replies) are strictly disabled.
- ⏰ **Deadline & Action Item Extraction**: Automatically extracts relative/absolute due dates and action requirements.

---

## 1. Setup Google Cloud OAuth 2.0 Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **Gmail Intelligence App**.
3. In the left sidebar, navigate to **APIs & Services > Library**. Search for **Gmail API** and click **Enable**.
4. Navigate to **APIs & Services > OAuth consent screen**:
   - Choose **External** (or Internal if using Workspace).
   - Fill in App Name & User Support Email.
   - Add Scope: `https://www.googleapis.com/auth/gmail.modify`.
   - Add your Gmail address as a **Test User**.
5. Navigate to **APIs & Services > Credentials**:
   - Click **Create Credentials > OAuth client ID**.
   - Select **Web application**.
   - Add Authorized redirect URIs:
     - Local testing: `http://localhost:8000/oauth2callback`
     - PythonAnywhere deployment: `https://<YOUR_USERNAME>.pythonanywhere.com/oauth2callback`
6. Click **Create** and download your client secrets JSON file. Save it as `credentials.json` in the root folder of this project (or populate `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env`).

---

## 2. Environment Configuration (`.env`)

Copy `.env.example` to `.env` and fill in your values:

```env
PORT=8000
SECRET_KEY=super-secret-key-change-this
BASE_URL=http://localhost:8000

# OAuth
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=http://localhost:8000/oauth2callback

# Safety Toggles
DRY_RUN=True
AUTO_LABEL=True
AUTO_ARCHIVE=False

# Confidence Thresholds
CONFIDENCE_AUTO_CLASSIFY=0.90
CONFIDENCE_FLAG_REVIEW=0.70

# Optional Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 3. Running Locally

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Unit Tests
```bash
python -m pytest
```

### Step 3: Start FastAPI Application
```bash
python main.py
```
Open your browser at `http://localhost:8000`. Click **Sign in with Google OAuth** to authenticate your Gmail account.

### Step 4: Run Background Sync via CLI
```bash
python sync_cli.py
```

---

## 4. Deploying to PythonAnywhere

1. Log in to [PythonAnywhere](https://www.pythonanywhere.com/).
2. Open a **Bash Console** and clone/upload your project repository.
3. Create a virtual environment and install requirements:
   ```bash
   mkvirtualenv --python=python3.10 gmail-env
   pip install -r requirements.txt
   ```
4. Create a **Web App**:
   - Go to the **Web** tab. Click **Add a new web app**.
   - Choose **Manual configuration** (or FastAPI/ASGI).
   - Set the Virtualenv path to `/home/<your-username>/.virtualenvs/gmail-env`.
   - Edit the **WSGI configuration file** to point to your `wsgi.py` file:
     ```python
     import sys
     import os

     path = '/home/<your-username>/Gmail-optimizer'
     if path not in sys.path:
         sys.path.insert(0, path)

     from main import app as application
     ```
5. In your Google Cloud Console OAuth Client settings, ensure `https://<your-username>.pythonanywhere.com/oauth2callback` is listed under **Authorized Redirect URIs**.
6. Set up a **Scheduled Task** in PythonAnywhere:
   - Go to **Tasks** tab.
   - Set a daily or hourly command:
     ```bash
     /home/<your-username>/.virtualenvs/gmail-env/bin/python /home/<your-username>/Gmail-optimizer/sync_cli.py
     ```

---

## 5. Dashboard UX Walkthrough

- **Today's Stats**: Instant metrics on Total Processed, Important Today, Action Required, Urgent, Needs Decision, and Upcoming Deadlines.
- **Needs Your Decision Queue**: Displays emails with prediction confidence $< 90\%$. Shows reasons why the prediction was made.
- **Teach System**: Select scope (*Only this email*, *All emails from this sender*, *Similar subjects*) and click **Accept Prediction** or **Change & Teach** to save preference rules.
- **Sync Gmail Now**: On-demand manual sync button to pull new emails and process classifications instantly.
