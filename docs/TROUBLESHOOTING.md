# CareerSync — Troubleshooting & Operational Guide

This document outlines common operational issues, diagnostic procedures, error tracebacks, and verified resolutions for **CareerSync**.

---

## 1. Presidio PII Redactor Failures (`FailClosedRedactionException`)

### Symptom
Application crashes during email ingestion with:
```text
app.ingestion.exceptions.FailClosedRedactionException: Presidio redaction failed: [E050] Can't find model 'en_core_web_sm'.
```

### Cause
The Microsoft Presidio analyzer engine requires spaCy's `en_core_web_sm` English language model, which has not been downloaded in the active Python environment.

### Solution
Run the spaCy model installer command:
```bash
python -m spacy download en_core_web_sm
```
Then rerun pytest or `main.py`.

---

## 2. Ollama Provider HTTP Failure (`RuntimeError`)

### Symptom
Ollama AI extraction fails with:
```text
RuntimeError: HTTP failure communicating with Ollama provider.
Request URL: http://localhost:11434/api/generate
Status Code: None
```

### Cause
The local Ollama LLM service is either not running, listening on a different port, or missing the configured model (`llama3.1:8b`).

### Diagnostic Commands
1. Check if Ollama service is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. Verify downloaded models:
   ```bash
   ollama list
   ```

### Solution
1. Start Ollama service: `ollama serve`
2. Pull the model: `ollama pull llama3.1:8b`
3. If using a different port or model, update `.env`:
   ```ini
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.1:8b
   ```

---

## 3. Presidio Over-Redaction (Resolved)

### History
Early builds registered a broad salutation regex that scrubbed job-title phrases
(e.g. "*for Software Engineer*") to `<PERSON>`, and a case-insensitive name
pattern that absorbed trailing words ("at Stripe") into the redacted span. This
masked company/role signals before entity resolution and caused 2 integration
tests to fail.

### Resolution
`app/ingestion/redactor.py` now scopes case-insensitivity to the salutation
prefix only and preserves phrases whose words are all job-role vocabulary
(`ROLE_VOCABULARY`). When a company name is still redacted to a placeholder
(e.g. `<LOCATION>`), `_extract_company_from_subject` detects the placeholder and
falls back to the sender-domain heuristic. All 71 tests now pass.

If you add new salutations or role titles, extend `ROLE_VOCABULARY` so legitimate
job titles are not over-redacted.

---

## 4. Google OAuth Authorization Errors

### Symptom
`RuntimeError: Failed to initialize Gmail client.` or missing authorization code.

### Cause
`credentials/google_oauth_client.json` is missing or invalid, or the browser callback timed out on port `8000`.

### Solution
1. Verify `credentials/google_oauth_client.json` exists and contains valid `client_id` and `client_secret`.
2. Ensure port `8000` is free on `localhost` for `app/auth/oauth_callback_server.py`.
3. Clear cached credentials database:
   ```bash
   rm auth_credentials.db
   ```
4. Re-run `python main.py --live` to re-trigger authorization.

---

## 5. SQLite Database File Locks

### Symptom
`sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`.

### Cause
Concurrent write attempts to `careersync.db` from multiple running instances of `main.py` or pytest.

### Solution
1. Terminate running `main.py` daemon processes.
2. In unit test fixtures, use isolated in-memory databases (`sqlite:///:memory:`) with `connect_args={"check_same_thread": False}` as implemented in `tests/test_career_sync_engine.py`.
