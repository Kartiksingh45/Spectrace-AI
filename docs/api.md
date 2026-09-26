# API reference

Base URL: `http://localhost:8000` in development. Full interactive docs (auto-generated from the
Pydantic schemas) are always available live at `/docs` (Swagger UI) and `/redoc`.

## Authentication

All endpoints except `/auth/register` and `/auth/login` require a valid session. The session is a
signed JWT stored in an `httpOnly` cookie (`spectrace_session`) set by register/login - there is no
`Authorization` header; the browser sends the cookie automatically (`credentials: "include"` on
the frontend's `fetch` calls). Requests without a valid cookie get `401 Unauthorized`.

Endpoints that also require a specific role are marked below (see also
[`app/api/deps.py`](../apps/api/app/api/deps.py) for the `require_reviewer` /
`require_administrator` dependencies).

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | none | Create a user (defaults to the `contributor` role) and start a session. |
| POST | `/auth/login` | none | Authenticate and start a session. |
| POST | `/auth/logout` | session | Clear the session cookie. |
| GET | `/auth/me` | session | Current user's profile. |
| POST | `/auth/change-password` | session | Change the current user's password. |
| GET | `/auth/users` | **administrator** | List all users. |
| PATCH | `/auth/users/{user_id}/role` | **administrator** | Change another user's role. |

**Example - register then read the session:**

```bash
curl -s -c cookies.txt -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"hunter2pass"}'

curl -s -b cookies.txt http://localhost:8000/auth/me
```

```json
{"id": "…", "email": "you@example.com", "role": "contributor", "created_at": "2026-…"}
```

## Projects

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/projects` | session | List projects the current user is a member of. |
| POST | `/projects` | session | Create a project (creator becomes its first member). |
| GET | `/projects/{project_id}` | member | Read one project. |
| PATCH | `/projects/{project_id}` | member | Rename a project. |
| DELETE | `/projects/{project_id}` | member | Delete a project and its data. |

A project a user is not a member of returns `404` (not `403`) from every endpoint below, so its
existence is never leaked to a non-member.

## Documents (requirements + code)

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/projects/{project_id}/documents` | member | Upload a requirement document (PDF/TXT/Markdown). Re-uploading the same filename creates a new **version** linked to the previous one, rather than an unrelated document. |
| POST | `/projects/{project_id}/codebases` | member | Upload and validate a source-code ZIP. |
| POST | `/projects/{project_id}/github-import` | member | Import a public GitHub repo (`{owner, repo, branch}`) - downloads its ZIP from GitHub's codeload endpoint (read-only, no token) and runs it through the same pipeline as a direct ZIP upload. |
| GET | `/projects/{project_id}/documents` | member | List documents and their processing status. |
| GET | `/projects/{project_id}/documents/{document_id}/diff?against={other_id}` | member | Unified diff between two versions of the same requirement document. Both must be `ready`. |
| DELETE | `/projects/{project_id}/documents/{document_id}` | member | Delete a document and its chunks. |

**Example - upload a requirement doc:**

```bash
curl -s -b cookies.txt -F "file=@requirements.md" \
  http://localhost:8000/projects/$PROJECT_ID/documents
```

```json
{"id": "…", "kind": "requirement", "filename": "requirements.md", "status": "ready",
 "error": null, "duration_ms": 143, "version": 1, "previous_version_id": null, "created_at": "2026-…"}
```

`status` is one of `uploaded` / `processing` / `ready` / `failed`; `error` is populated only when
`status == "failed"`. `duration_ms` is how long ingestion (parse + chunk + embed) took.

**Example - import a public repo:**

```bash
curl -s -b cookies.txt -X POST http://localhost:8000/projects/$PROJECT_ID/github-import \
  -H "Content-Type: application/json" \
  -d '{"owner":"octocat","repo":"demo","branch":"main"}'
```

## Retrieval

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/projects/{project_id}/search` | member | Semantic search, filtered by content type. |

```bash
curl -s -b cookies.txt -X POST http://localhost:8000/projects/$PROJECT_ID/search \
  -H "Content-Type: application/json" \
  -d '{"query":"mobile OTP verification","content_type":"all"}'
```

`content_type` is one of `requirement` / `code` / `all`. Each result includes `chunk_id`,
`document_id`, `filename`, `content_type`, `text`, `score`, and `source_metadata` (page number for
requirements; file path/symbol/line range for code). Ranking is hybrid: a wide candidate pool is
pulled by cosine similarity, blended with a lexical keyword-overlap score, then reordered (not
rescored - `score` stays the hybrid value) by a cross-encoder reranker over the leading candidates
(see `app/services/retrieval.py` and `app/services/reranker.py`).

## Change requests and agent runs

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/projects/{project_id}/requests` | member | Create a change request. |
| GET | `/projects/{project_id}/requests` | member | List a project's change requests, with each one's latest run/plan summary. |
| POST | `/requests/{request_id}/analyse` | member | Start (or resume, idempotently) an agent run. Blocks until the run finishes or pauses. |
| GET | `/requests/{request_id}/events` | member | Server-Sent Events stream of that change request's live run progress - open this *alongside* `analyse`/`clarification`/`decision`, not instead of it; it only reads. |
| GET | `/runs/{run_id}` | member | Read a run's status, timeline, evidence, and generated plan. |
| POST | `/runs/{run_id}/clarification` | member | Answer a pending clarification question and resume. |
| POST | `/plans/{plan_id}/decision` | **reviewer/administrator** | Approve, edit-and-approve, reject, or request regeneration. |

A `RunOut` response looks like:

```json
{
  "id": "…", "change_request_id": "…", "status": "awaiting_approval",
  "steps": [
    {"step_index": 0, "tool_name": null, "input_summary": "Add mobile OTP…",
     "output_summary": "Classified as feature", "status": "ok", "duration_ms": 0},
    {"step_index": 1, "tool_name": "search_requirements", "input_summary": "{\"query\": \"OTP\"}",
     "output_summary": "[chunk 1] …", "status": "ok", "duration_ms": 812}
  ],
  "pending_question": null,
  "generated_plan": { "summary": "…", "confidence": "high", "affected_files": [...], "...": "..." },
  "plan_id": "…",
  "started_at": "2026-09-22T10:00:00Z", "ended_at": null, "duration_ms": null
}
```

`ended_at`/`duration_ms` are `null` while a run is still open (waiting on clarification or
approval); they're set once the run reaches `completed` or `failed`.

`POST /plans/{plan_id}/decision` accepts:

```json
{"decision": "approved" | "edit_approved" | "rejected" | "regenerate_requested",
 "feedback": "optional string, used for rejected/regenerate_requested",
 "final_content": "optional full GeneratedPlan object, required for edit_approved"}
```

**`GET /requests/{request_id}/events`** streams standard SSE frames while the run is `running`,
one per newly-persisted step:

```
data: {"step_index": 1, "tool_name": "search_requirements", "input_summary": "...", "output_summary": "...", "status": "ok"}

data: {"step_index": 2, "tool_name": "generate_plan", "input_summary": "...", "output_summary": "...", "status": "ok"}

event: done
data: {"status": "awaiting_approval"}
```

The stream closes after the `done` event (or after a 5-minute safety cap if a connection is left
open with nothing left to report).

## Errors

Errors are returned as `{"detail": "message"}` with a standard HTTP status code: `400` for
validation/state errors (e.g. deciding on a plan that isn't awaiting a decision), `401` for no/
invalid session, `403` for a role check failure, `404` for a missing or inaccessible resource,
`409` for a conflicting register (email already in use).
