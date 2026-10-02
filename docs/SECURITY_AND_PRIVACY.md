# CareerSync — Security & Privacy Specification

This document details the verified security and privacy architecture of **CareerSync**, focusing on secret management, Google OAuth 2.0 authorization, Microsoft Presidio PII redaction, logging safeguards, and data retention policies.

---

## 1. Secrets & Credentials Management

### 1.1 In-Memory & Encrypted Credential Stores
* **Development / Test Environment**: `MemoryCredentialStore` (`app/auth/credential_store.py`) keeps OAuth credentials in ephemeral memory.
* **Persistent Authentication**: Credentials stored in SQLite database `auth_credentials.db` (configured via `AuthConfig` in `app/infrastructure/config/auth_config.py`).
* **Token Encryption**: Supported via optional Fernet symmetric encryption using the `ENCRYPTION_KEY` environment variable.

### 1.2 Confidential Files & `.gitignore` Safeguards
The following files contain sensitive authentication data and are strictly excluded from version control via `.gitignore`:
* `.env` — Environment secret overrides.
* `credentials/google_oauth_client.json` — Google OAuth Client ID and Secret.
* `auth_credentials.db` — OAuth access & refresh tokens.
* `careersync.db` — Local SQLite operational database.

---

## 2. Google OAuth 2.0 Authorization & Token Handling

### 2.1 Scope Minimization
CareerSync requests the minimum required OAuth scope for email triage and folder management:
* **Requested Scope**: `https://www.googleapis.com/auth/gmail.modify`
* **Permissions Granted**: Read incoming emails, apply/remove Gmail labels, modify email thread locations, mark messages as read/archived.
* **Excluded Scopes**: Full account access, delete message scope, send email scope, Google Drive scope.

### 2.2 PKCE Authentication Flow
Authorization is conducted using OAuth 2.0 Authorization Code Flow with Proof Key for Code Exchange (PKCE) (`app/auth/oauth_service.py`):
1. Client generates a cryptographically secure PKCE `code_verifier` and `code_challenge`.
2. Browser opens authorization URL requesting authorization code.
3. Local HTTP callback server (`app/auth/oauth_callback_server.py`) listens on `http://localhost:8000/auth/callback` to capture authorization code.
4. Authorization code is exchanged for access and refresh tokens. Access tokens are automatically refreshed upon expiry.

---

## 3. Presidio PII Privacy Boundary (D2)

CareerSync enforces a mandatory **Privacy-First Invariant**:
> *No raw email body, candidate name, phone number, physical address, or personal email address may be transmitted to external or local LLM inference engines.*

### 3.1 Presidio Analyzer & Anonymizer Implementation
The privacy boundary is implemented in `app/ingestion/redactor.py` using Microsoft Presidio (`PresidioAnalyzer` + `PresidioAnonymizer`):
* **Supported PII Entities Anonymized**:
  - `PERSON` $\rightarrow$ Replaced with `<PERSON>`
  - `EMAIL_ADDRESS` $\rightarrow$ Replaced with `<EMAIL_ADDRESS>`
  - `PHONE_NUMBER` $\rightarrow$ Replaced with `<PHONE_NUMBER>`
  - `LOCATION` $\rightarrow$ Replaced with `<LOCATION>`
  - Custom regex patterns for candidate identifiers.

### 3.2 Fail-Closed Security Boundary
In `app/ingestion/service.py`, redaction is enforced fail-closed:
```python
try:
    redacted_email = self.redactor.redact_email(raw_email)
except Exception as exc:
    raise FailClosedRedactionException(f"Redaction failed: {exc}")
```
If Presidio fails to analyze or anonymize an email payload (e.g. missing language model or runtime exception), the payload is discarded immediately. Unredacted text is never written to disk or sent downstream.

---

## 4. Logging & PII Protection

### Logging Rules
* **No Raw Email Logging**: `main.py` and processing services log operational metadata (Message ID, category, decision audit status, execution duration), but **never log raw email bodies or unscrubbed candidate PII**.
* **Log Level**: Default logging level is set to `INFO`.

---

## 5. Data Retention & Persistence

* **Operational State Retention**: Active applications, opportunities, and state transition records persist indefinitely in the local `careersync.db` SQLite database until manually deleted or reset.
* **Message Ledger Retention**: Message IDs are retained in `processed_messages` to guarantee processing idempotency across continuous polling cycles.
