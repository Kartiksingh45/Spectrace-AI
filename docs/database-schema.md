# Database schema

Postgres, managed via SQLAlchemy models + Alembic migrations (`apps/api/alembic/versions/`).
`pgvector` provides the vector column/index on `content_chunks`. LangGraph's own checkpointer
(`langgraph-checkpoint-postgres`) manages a separate set of tables (`checkpoints`,
`checkpoint_writes`, `checkpoint_blobs`, ...) in the same database via its own `.setup()` call,
not an Alembic migration - they aren't listed here since they're an implementation detail of
pause/resume, not application data.

## Tables

### `users`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| email | varchar(255), unique, indexed | |
| password_hash | varchar(255) | bcrypt |
| role | enum `user_role` (`contributor`/`reviewer`/`administrator`) | default `contributor` |
| created_at | timestamptz | |

### `projects`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| name | varchar(255) | |
| owner_id | uuid, FK → users.id | |
| created_at | timestamptz | |

### `project_members`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| project_id | uuid, FK → projects.id | |
| user_id | uuid, FK → users.id | |
| joined_at | timestamptz | |

Unique constraint on `(project_id, user_id)`. Every query that touches project data joins through
this table (`app/api/deps.py::get_membership`) so one project can never retrieve another's content
- a project a user isn't a member of returns `404`, not `403`, from every endpoint.

### `documents`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| project_id | uuid, FK → projects.id | |
| kind | enum `content_kind` (`requirement`/`code`) | |
| filename | varchar(255) | |
| status | enum `document_status` (`uploaded`/`processing`/`ready`/`failed`) | |
| error | text, nullable | populated when `status == failed` |
| duration_ms | integer, nullable | ingestion (parse + chunk + embed) wall time |
| version | integer | starts at 1; incremented when a requirement doc with the same filename is re-uploaded |
| previous_version_id | uuid, FK → documents.id, nullable | links a re-upload to the version it supersedes |
| full_text | text, nullable | requirement docs only - the whole extracted text (independent of chunk boundaries), diffed by `GET .../documents/{id}/diff` |
| created_at | timestamptz | |

### `content_chunks`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| project_id | uuid, FK → projects.id | denormalized for a single-join, project-scoped search query |
| document_id | uuid, FK → documents.id | |
| content_type | enum `content_kind` | matches the parent document's kind |
| text | text | the chunk itself |
| embedding | `vector(384)` (pgvector) | dimension from `EMBEDDING_DIMENSIONS`; default model is `all-MiniLM-L6-v2` |
| source_metadata | jsonb | requirement chunks: `{filename, page_number}`; code chunks: `{file_path, symbol, start_line, end_line, language}` |
| created_at | timestamptz | |

Search (`app/services/retrieval.py`) runs a cosine-distance query (`embedding <=> query_vector`)
filtered by `project_id` and `content_type`, ordered by distance, above `MIN_RELEVANCE_SCORE`.

### `change_requests`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| project_id | uuid, FK → projects.id | |
| created_by | uuid, FK → users.id | |
| request_text | text | |
| request_type | enum `request_type` (`feature`/`bug`/`refactor`/`security`/`performance`/`documentation`), nullable | set once the agent classifies it |
| status | enum `change_request_status` (`pending`/`analysing`/`awaiting_clarification`/`awaiting_approval`/`approved`/`rejected`/`failed`) | |
| created_at | timestamptz | |

### `agent_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| change_request_id | uuid, FK → change_requests.id | |
| thread_id | varchar(64), unique | LangGraph checkpointer thread id - resuming a run replays against this thread |
| status | enum `agent_run_status` (`running`/`awaiting_clarification`/`awaiting_approval`/`completed`/`failed`) | |
| started_at | timestamptz | |
| ended_at | timestamptz, nullable | set once the run reaches `completed`/`failed`; `ended_at - started_at` is the run's total duration |

### `agent_steps`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| run_id | uuid, FK → agent_runs.id | |
| step_index | integer | display order in the run's timeline |
| tool_name | varchar(64), nullable | `null` for the initial classification step |
| input_summary | text | truncated to 500 chars |
| output_summary | text | truncated to 500 chars |
| duration_ms | integer | wall time for that specific tool call, timed via a LangChain callback (`ToolTimingCallback` in `app/services/agent_runner.py`) |
| status | enum `agent_step_status` (`ok`/`error`) | |
| created_at | timestamptz | |

### `generated_plans`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| change_request_id | uuid, FK → change_requests.id | |
| run_id | uuid, FK → agent_runs.id | |
| version | integer | increments on each `regenerate_requested` decision |
| content | jsonb | the full structured plan - summary, evidence, affected_files, user_story, acceptance_criteria, tasks, test_cases, assumptions, risks, confidence |
| created_at | timestamptz | |

### `approvals`

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid, PK | |
| plan_id | uuid, FK → generated_plans.id | |
| reviewer_id | uuid, FK → users.id | |
| decision | enum `approval_decision` (`approved`/`edit_approved`/`rejected`/`regenerate_requested`) | |
| feedback | text, nullable | used for `rejected`/`regenerate_requested` |
| final_content | jsonb, nullable | the reviewer's edited plan, for `edit_approved` - becomes the plan of record |
| created_at | timestamptz | the audit trail: who decided, when, and what |

## Indexes

- `users.email` - unique index (login lookup).
- `project_members(project_id, user_id)` - unique constraint (membership lookup/isolation).
- `content_chunks.project_id` - indexed (every search query filters by it first).
- `agent_runs.thread_id` - unique index (checkpointer resume lookup).

## Migration history

| Revision | Adds |
| --- | --- |
| `0001_initial` | `users`, `projects`, `project_members` |
| `0002_ingestion` | `documents`, `content_chunks` (+ pgvector extension) |
| `0003_agent_workflow` | `change_requests`, `agent_runs`, `agent_steps`, `generated_plans`, `approvals` |
| `0004_evaluation` | `evaluation_cases`, `evaluation_results` (built for the evaluation harness) |
| `0005_remove_evaluation` | drops `evaluation_cases`/`evaluation_results` - the feature was removed |
| `0006_document_duration` | adds `documents.duration_ms` |
| `0007_document_versioning` | adds `documents.version`, `documents.previous_version_id`, `documents.full_text` |
