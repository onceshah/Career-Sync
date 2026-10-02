# CareerSync — System Configuration Reference

This document provides a comprehensive reference for all configuration parameters, environment variables, YAML policy rules, and runtime command-line flags in **CareerSync**.

---

## 1. Environment Variable Reference

The system loads environment settings via `python-dotenv` or system environment variables:

| Environment Variable | Required? | Default Value | Purpose | Consumption Source |
|---|---|---|---|---|
| `DATABASE_URL` | No | `sqlite:///careersync.db` | Connection string for SQLAlchemy ORM persistence database. | [`app/infrastructure/persistence/database.py`](../app/infrastructure/persistence/database.py) |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Base HTTP endpoint for the local Ollama LLM provider. | [`app/ai/providers/ollama.py`](../app/ai/providers/ollama.py) |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Ollama model identifier used for entity extraction prompts. | [`app/ai/providers/ollama.py`](../app/ai/providers/ollama.py) |
| `ENCRYPTION_KEY` | No | `None` | Optional master secret key for Fernet token encryption. | [`app/infrastructure/config/auth_config.py`](../app/infrastructure/config/auth_config.py) |
| `CALENDAR_PROVIDER` | No | `memory` | Calendar backend: `memory` (in-process, no external writes) or `google` (Google Calendar v3). | [`app/api/app.py`](../app/api/app.py) |

### 1.1 OAuth Scopes
`AuthConfig.scopes` requests `gmail.modify` (ingestion) and `calendar.events` (D8 calendar writes) by default.

---

## 2. Policy Rules YAML Reference (`app/config/policy_rules.yaml`)

CareerSync uses declarative YAML configuration (`app/config/policy_rules.yaml`) to govern rule-based email pre-filtering, taxonomy mapping, and label prefixes.

### 2.1 Taxonomy Configuration

```yaml
taxonomy:
  folders:
    LEADS: "Career/Leads"
    APPLICATIONS: "Career/Applications"
    ASSESSMENTS: "Career/Assessments"
    INTERVIEWS: "Career/Interviews"
    OFFERS: "Career/Offers"
    REJECTIONS: "Career/Rejections"
    ARCHIVE: "Career/Archive"

  vendors:
    INDEED: "Indeed"
    UNSTOP: "Unstop"
    LINKEDIN: "LinkedIn"
    GLASSDOOR: "Glassdoor"
    GREENHOUSE: "Greenhouse"
    LEVER: "Lever"

  categories:
    JOB_OPPORTUNITY: "Job Opportunity"
    ONLINE_ASSESSMENT: "Online Assessment"
    INTERVIEW_INVITE: "Interview Invite"
    JOB_OFFER: "Job Offer"
    REJECTION: "Rejection"

  label_prefixes:
    priority: "Priority"
    importance: "Importance"
    vendor: "Platform"
    project: "Project"
    category: "Category"
```

### 2.2 Rule Rules Matrix

| Rule ID | Name | Conditions | Target Actions |
|---|---|---|---|
| `RULE-PLATFORM-INDEED` | Identify Indeed Communication | `sender_domain: indeed.com, indeedemail.com` | `vendor: INDEED` |
| `RULE-PLATFORM-UNSTOP` | Identify Unstop Communication | `sender_domain: unstop.com` | `vendor: UNSTOP` |
| `RULE-PLATFORM-LINKEDIN` | Identify LinkedIn Jobs | `sender_domain: linkedin.com, lnkd.in` | `vendor: LINKEDIN` |
| `RULE-PLATFORM-GLASSDOOR` | Identify Glassdoor | `sender_domain: glassdoor.com` | `vendor: GLASSDOOR` |
| `RULE-PLATFORM-GREENHOUSE` | Identify Greenhouse ATS | `sender_domain: greenhouse.io, greenhouse.com` | `vendor: GREENHOUSE` |
| `RULE-PLATFORM-LEVER` | Identify Lever ATS | `sender_domain: lever.co, jobs.lever.co` | `vendor: LEVER` |
| `RULE-CAT-REJECTION-SUBJECT` | Detect Rejections (subject) | `subject_contains: regret to inform, not selected, unfortunately, not moving forward, update on your application, application status` | `folder: REJECTIONS`, `category: REJECTION`, `priority: LOW`, `flag: false` |
| `RULE-CAT-REJECTION-BODY` | Detect Rejections (body) | `body_contains: unfortunate, other candidates, not match, no longer under consideration` | `folder: REJECTIONS`, `category: REJECTION`, `priority: LOW`, `flag: false` |
| `RULE-CAT-ASSESSMENT` | Detect Coding Tests | `subject_contains: assessment, coding test, online test, hackerrank, codility, glider, test link, take home` | `folder: ASSESSMENTS`, `category: ONLINE_ASSESSMENT`, `priority: HIGH`, `flag: true` |
| `RULE-CAT-INTERVIEW` | Detect Interviews | `subject_contains: interview, schedule, zoom, discussion, availability, recruiter screen` | `folder: INTERVIEWS`, `category: INTERVIEW_INVITE`, `priority: HIGH`, `flag: true` |
| `RULE-CAT-OFFER` | Detect Job Offers | `subject_contains: offer letter, your offer, congratulations, compensation, joining details, offer`<br/>`body_contains: offer letter, compensation, salary, joining date, we are pleased to offer` | `folder: OFFERS`, `category: JOB_OFFER`, `priority: URGENT`, `flag: true`, `is_override_allowed: false` |
| `RULE-NON-CAREER` | Archive Marketing / Digests | `subject_contains: unsubscribe, newsletter, promotional, weekly digest, product update`<br/>`body_contains: unsubscribe, promo code, 20% off, referral code` | `folder: ARCHIVE`, `categories: []`, `is_override_allowed: false` |

---

## 3. Command-Line Arguments (`main.py`)

The application entrypoint (`main.py`) accepts the following CLI flags:

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--live` | boolean flag | `False` | Enables live execution mode (applies real Gmail label mutations and database updates). |
| `--limit` | integer | `5` | Specifies maximum number of emails processed per batch/cycle. |
| `--daemon` | boolean flag | `False` | Runs continuous background polling service until SIGINT/SIGTERM. |
