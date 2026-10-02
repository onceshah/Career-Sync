# CareerSync — Reproducible Local & Docker Setup Guide

This guide provides verified, step-by-step instructions for setting up and running **CareerSync** locally and in a Docker container environment.

---

## 1. System Requirements & Prerequisites

Before setting up CareerSync, verify that your environment meets the following requirements:

* **Operating System**: Windows 10/11, macOS, or Linux
* **Python**: Python 3.12 or higher (`python --version`)
* **Git**: Installed (`git --version`)
* **Ollama**: Installed and running locally (Download from [ollama.ai](https://ollama.ai))
* **Docker** *(Optional)*: Docker Desktop installed for containerized execution

---

## 2. Step-by-Step Local Setup

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd careersync
```

### Step 2: Create Python Virtual Environment
```bash
# Create virtual environment named 'venv'
python -m venv venv

# Activate on Windows (PowerShell / CMD):
venv\Scripts\activate

# Activate on macOS / Linux:
# source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Download mandatory spaCy language model for Presidio PII Redactor
python -m spacy download en_core_web_sm
```

### Step 4: Environment Configuration
Copy `.env.example` to create `.env`:
```bash
cp .env.example .env
```

Verify contents of `.env`:
```ini
DATABASE_URL=sqlite:///careersync.db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
# ENCRYPTION_KEY=
```

---

## 3. Local LLM Setup (Ollama)

CareerSync requires a running Ollama server for AI entity extraction (D3):

1. **Start Ollama Service**:
   Ensure the Ollama application is active and running on `http://localhost:11434`.

2. **Pull Required Model**:
   ```bash
   ollama pull llama3.1:8b
   ```
   *(Alternatively, `ollama pull llama3.2` can be used if configured in `.env`)*

3. **Verify Ollama Endpoint**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

---

## 4. Google OAuth 2.0 Credentials Setup (Optional for Live Mode)

To run in live mode with Gmail ingestion:

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new OAuth 2.0 Client ID with application type **Desktop app**.
3. Download the credentials JSON file.
4. Save the file to the repository path:
   ```text
   credentials/google_oauth_client.json
   ```
5. On initial execution with `--live`, a browser window will open requesting Gmail authorization (`https://www.googleapis.com/auth/gmail.modify`). OAuth tokens will be cached locally in `auth_credentials.db`.

---

## 5. Running the Application

### 5.1 Run Automated Tests
```bash
pytest
```
*(Runs 71 test cases across unit, state machine, matcher, API, persistence, and integration tests)*

### 5.2 Single Execution Cycle (Dry-Run Mode)
```bash
python main.py --limit 5
```
Processes up to 5 emails in simulated dry-run mode without mutating Gmail inbox state.

### 5.3 Single Execution Cycle (Live Gmail Mode)
```bash
python main.py --live --limit 10
```
Processes up to 10 emails, applying real Gmail labels and database updates.

### 5.4 Continuous Daemon Mode
```bash
python main.py --daemon --limit 5
```
Runs a continuous polling loop processing emails in batches. Press `Ctrl+C` for graceful shutdown.

---

## 6. Docker Setup & Execution

CareerSync includes a production `Dockerfile` for containerized execution.

### Step 1: Build Docker Image
```bash
docker build -t careersync:latest .
```

### Step 2: Run Docker Container (Dry-Run Mode)
```bash
docker run --rm \
  -e DATABASE_URL=sqlite:////app/data/careersync.db \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v ./credentials:/app/credentials \
  careersync:latest python main.py --limit 5
```
*(Note: `host.docker.internal` allows the Docker container to access Ollama running on the host machine).*
