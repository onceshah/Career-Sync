# CareerSync — Database & Persistence Specification

This document describes the database schema, ORM entity relationships, repository contracts, and migration procedures implemented in **CareerSync**.

---

## 1. Database Overview

CareerSync uses **SQLite** as its operational relational database engine, managed via **SQLAlchemy 2.0 ORM** (`app/infrastructure/persistence/`).

* **Database File Path**: `careersync.db` (Configurable via `DATABASE_URL` environment variable).
* **Test Isolation**: In-memory SQLite instances (`sqlite:///:memory:`) are instantiated per test session.
* **Repository Pattern**: `ATSRepository` (`app/infrastructure/persistence/repository.py`) encapsulates all ATS database queries and transaction boundaries; `CalendarRepository` (`app/infrastructure/persistence/calendar_repository.py`) does the same for calendar event proposals.

---

## 2. Implemented Schema & Entity Relationship Diagram

```text
+------------------------+           +------------------------+
|      opportunities     |           |      applications      |
+------------------------+           +------------------------+
| PK id (String)         |           | PK id (String)         |
|    company_name (Str)  |           |    company_name (Str)  |
|    job_title (Str)     |           |    job_title (Str)     |
|    platform (Str)      |           |    platform (Str)      |
|    is_promoted (Bool)  |           |    application_ref_id  |
|    source_email_id(Str)|           |    current_state (Enum)|
|    discovered_at(DTime)|           |    review_status (Enum)|
+------------------------+           |    created_at (DateTime|
                                     |    updated_at (DateTime|
                                     +-----------+------------+
                                                 | 1
                                                 |
                                                 | N
                                     +-----------v------------+
                                     |    state_transitions   |
                                     +------------------------+
                                     | PK id (String)         |
                                     | FK application_id (Str)|
                                     |    previous_state(Enum)|
                                     |    new_state (Enum)    |
                                     |    triggering_msg_id   |
                                     |    evidence_snippet    |
                                     |    review_status (Enum)|
                                     |    reasoning (Text)    |
                                     |    timestamp (DateTime)|
                                     +------------------------+
                                                 | 1
                                                 |
                                                 | N
                                     +-----------v----------------+
                                     |  calendar_event_proposals  |
                                     +----------------------------+
                                     | PK id (String)             |
                                     | FK application_id (Str)    |
                                     |    event_type (Enum)       |
                                     |    title / description     |
                                     |    start_at / end_at       |
                                     |    status (Enum)           |
                                     |    provider / event_id     |
                                     |    note / decided_at       |
                                     +----------------------------+

+------------------------+           +------------------------+
|   processed_messages   |           |    auth_credentials    |
+------------------------+           +------------------------+
| PK message_id (String) |           | PK user_id (String)    |
|    processed_at (DTime)|           |    provider (String)   |
|    status (String)     |           |    tokens_json (Text)  |
+------------------------+           |    updated_at (DTime)  |
                                     +------------------------+
```

---

## 3. Table Definitions & Column Details

### 3.1 `opportunities` Table
Stores discovered job postings prior to formal candidate application submission.
* `id` (`VARCHAR(36)`, Primary Key): UUID v4 identifier.
* `company_name` (`VARCHAR(255)`, Not Null): Target company name.
* `job_title` (`VARCHAR(255)`, Not Null): Target position title.
* `platform` (`VARCHAR(100)`): Source job platform (e.g. LinkedIn, Indeed).
* `requisition_id` (`VARCHAR(100)`): Optional platform requisition ID.
* `source_email_id` (`VARCHAR(255)`): Triggering Gmail Message ID.
* `created_at` (`DATETIME`): UTC creation timestamp.

### 3.2 `applications` Table
Tracks active job applications and their canonical lifecycle state.
* `id` (`VARCHAR(36)`, Primary Key): UUID v4 application identifier.
* `company_name` (`VARCHAR(255)`, Not Null): Target company name.
* `job_title` (`VARCHAR(255)`, Not Null): Position title.
* `platform` (`VARCHAR(100)`): Source job platform.
* `application_ref_id` (`VARCHAR(100)`, Unique): Requisition / job reference code used for Tier-1 entity matching.
* `current_state` (`Enum(ApplicationLifecycleState)`, Not Null): Lifecycle state (`DISCOVERED`, `INTERESTED`, `APPLIED`, `ASSESSMENT`, `INTERVIEW`, `OFFER_SELECTED`, `REJECTED`, `WITHDRAWN`, `EXPIRED`).
* `review_status` (`Enum(ReviewStatus)`, Not Null): Review flag (`CONFIRMED`, `NEEDS_REVIEW`, `RESOLVED`).
* `created_at` (`DATETIME`): UTC creation timestamp.
* `updated_at` (`DATETIME`): UTC last update timestamp.

### 3.3 `state_transitions` Table
Maintains an immutable audit ledger of every state machine transition attempt.
* `id` (`VARCHAR(36)`, Primary Key): UUID v4 transition ID.
* `application_id` (`VARCHAR(36)`, Foreign Key $\rightarrow$ `applications.id`): Target application ID.
* `previous_state` (`Enum(ApplicationLifecycleState)`, Not Null): Pre-transition state.
* `new_state` (`Enum(ApplicationLifecycleState)`, Not Null): Proposed state.
* `triggering_message_id` (`VARCHAR(255)`): Gmail Message ID triggering transition (unique per application).
* `evidence_snippet` (`TEXT`): Short evidence snippet (email subject) backing the transition.
* `review_status` (`Enum(ReviewStatus)`, Not Null): `CONFIRMED` or `NEEDS_REVIEW`.
* `reasoning` (`TEXT`): Decision audit explanation (e.g. state machine transition reason and 6-tier matching tier explanation).
* `timestamp` (`DATETIME`): UTC execution timestamp.

### 3.4 `processed_messages` Table
Guarantees message processing idempotency across background polling cycles.
* `message_id` (`VARCHAR(255)`, Primary Key): Gmail unique message ID.
* `processed_at` (`DATETIME`): UTC processing timestamp.
* `status` (`VARCHAR(100)`): Processing outcome status (`APPLICATION_CREATED`, `APPLICATION_UPDATED`, `OPPORTUNITY_DISCOVERED`, `ARCHIVED_NON_CAREER`, `NEEDS_REVIEW_STAGED`).

### 3.5 `calendar_event_proposals` Table (D8)
Stages calendar events derived from applications for human-in-the-loop approval.
* `id` (`VARCHAR(36)`, Primary Key): Proposal identifier.
* `application_id` (`VARCHAR(36)`, Foreign Key $\rightarrow$ `applications.id`, `ON DELETE CASCADE`): Owning application.
* `event_type` (`Enum(CalendarEventType)`, Not Null, CHECK): `INTERVIEW`, `ASSESSMENT_DEADLINE`, `OFFER_DEADLINE`, `FOLLOW_UP`.
* `title` / `description` (`VARCHAR` / `TEXT`): Event content.
* `start_at` / `end_at` (`DATETIME`, Not Null): Event window.
* `status` (`Enum(ProposalStatus)`, Not Null, CHECK, indexed): `PENDING`, `CREATED`, `REJECTED`, `FAILED`.
* `provider` / `provider_event_id` (`VARCHAR`): Provider name and created external event id.
* `note` (`TEXT`): Reviewer note or provider error message.
* `created_at` / `decided_at` (`DATETIME`): Staging and decision timestamps.

---

## 4. Repository Interface (`ATSRepository`)

`ATSRepository` (`app/infrastructure/persistence/repository.py`) exposes high-level Python methods:

* `create_opportunity(opp: Opportunity) -> OpportunityORM`: Inserts a new opportunity.
* `create_application(app: Application) -> ApplicationORM`: Inserts a new application record.
* `update_application_state(app_id: str, new_state: ApplicationLifecycleState, review_status: ReviewStatus) -> ApplicationORM`: Mutates state and updates timestamp.
* `record_transition(txn: StateTransitionRecord) -> StateTransitionORM`: Appends an audit entry.
* `list_active_applications() -> List[ApplicationORM]`: Fetches active non-archived applications.
* `is_message_processed(message_id: str) -> bool`: Idempotency lookup.
* `mark_message_processed(message_id: str, status: str)`: Idempotency ledger insertion.

### 4.1 Repository Interface (`CalendarRepository`)
* `create_proposal(proposal: CalendarEventProposal) -> CalendarEventProposal`: Stages a PENDING proposal.
* `get_proposal(proposal_id: str) -> Optional[CalendarEventProposal]`: Fetch a proposal.
* `list_proposals(status: Optional[ProposalStatus]) -> List[CalendarEventProposal]`: List/filter proposals (newest first).
* `update_proposal_status(proposal_id, status, provider, provider_event_id, note)`: Records an approval/rejection/failure.

---

## 5. Database Initialization & Reset Procedure

Database tables are initialized automatically upon `CareerSyncEngine` instantiation via `init_db()` in `app/infrastructure/persistence/database.py`:

```python
from app.infrastructure.persistence.database import init_db, reset_db

# Initialize tables if not present
init_db()

# Reset database (Drops and recreates all tables)
reset_db()
```
