# Spectrace AI

Agentic SDLC and codebase intelligence platform. A user uploads requirement documents and a source-code
project, submits a change request in natural language, and Spectrace AI retrieves relevant evidence from
both the documents and the codebase, proposes affected files, and generates a user story with acceptance
criteria and test cases — all grounded in cited evidence and gated behind human reviewer approval.

See [`Spectrace_AI_BRD.docx`](Spectrace_AI_BRD.docx) for the full Business Requirements Document.

## Architecture

```
Next.js (apps/web)  →  FastAPI (apps/api)  →  Postgres + pgvector (cloud: Neon or Supabase)
                                            →  Gemini (LLM)
                                            →  sentence-transformers (embeddings)
```

| Layer          | Technology                                  |
| -------------- | -------------------------------------------- |
| Frontend       | Next.js (App Router) + TypeScript + Tailwind |
| API            | Python + FastAPI + SQLAlchemy + Alembic      |
| Database       | Postgres (Neon / Supabase free tier)         |
| Vector search  | pgvector extension on the same Postgres      |
| Agent          | LangGraph                                    |
| LLM            | Gemini                                       |
| Embeddings     | sentence-transformers (local, no API key)    |

The app talks to Postgres directly through SQLAlchemy/Alembic — no vendor BaaS SDK (auth, storage
client, etc.) is used, even when the database is hosted on Supabase. This is a deliberate constraint from
the BRD to build backend engineering depth rather than depend on a managed backend platform.

## Current status

- [x] Monorepo scaffold, backend and frontend booting locally
- [x] User registration / login / logout (httpOnly session cookie)
- [x] Project create / list / rename / delete, isolated per user
- [x] Requirement document ingestion (PDF/TXT/Markdown → chunks → embeddings)
- [x] Source-code ZIP ingestion (safe-path validation → chunks → embeddings)
- [x] Semantic search endpoint (pgvector cosine similarity, project + content-type scoped)
- [x] LangGraph agent workflow (classify → tool-calling loop → deterministic grounding review →
      human approval), with real `interrupt()`/resume for clarification and approval
- [x] Human review workflow (approve / edit-and-approve / reject / regenerate)
- [x] Role enforcement (only `reviewer`/`administrator` may decide on a plan; only
      `administrator` may list/manage users)
- [x] Structured logging (run/step/ingestion id, duration, status) and recorded run/step/document durations
- [x] Deployment config (Dockerfiles, `docker-compose.yml`, `render.yaml`, `vercel.json` - see
      [Deployment](#deployment))
- [x] Optional: hybrid (vector + keyword) search with a cross-encoder reranker
- [x] Optional: read-only GitHub repository import alongside ZIP/folder upload
- [x] Optional: live agent progress via Server-Sent Events (`GET /requests/{id}/events`)
- [x] Optional: export an approved plan to Markdown or PDF
- [x] Optional: requirement-document version comparison (diff between re-uploads)
- [ ] Evaluation dataset and metrics (built, then deliberately removed - see below)

The evaluation harness (BRD §10: `evaluation_cases`/`evaluation_results`, metrics, an Evaluation
page) was built and then intentionally removed - it didn't fit this app's actual workflow well
enough to justify keeping. See `apps/api/alembic/versions/0004_evaluation.py` /
`0005_remove_evaluation.py` for the add-then-remove history.

## Setup

### 1. Database

Create a free Postgres project on [Neon](https://neon.tech) or [Supabase](https://supabase.com) and copy
its connection string.

### 2. Backend (`apps/api`)

```bash
cd apps/api
python -m venv .venv
./.venv/Scripts/activate        # or: source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env
# edit .env: paste your DATABASE_URL, set a real JWT_SECRET

alembic upgrade head             # creates users/projects/project_members, then documents/content_chunks + pgvector
uvicorn app.main:app --reload    # http://localhost:8000
```

Run tests (uses an in-memory SQLite DB, no cloud connection needed):

```bash
pytest
```

### Verifying ingestion + search

Once `DATABASE_URL` points at a real Postgres and the migration has run:

```bash
# Register + log in (keep the cookie jar for the authenticated calls below)
curl -s -c cookies.txt -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" -d '{"email":"you@example.com","password":"hunter2pass"}'

# Create a project
PROJECT_ID=$(curl -s -b cookies.txt -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" -d '{"name":"Demo"}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# Upload a requirement doc and a code ZIP
curl -s -b cookies.txt -F "file=@requirements.md" http://localhost:8000/projects/$PROJECT_ID/documents
curl -s -b cookies.txt -F "file=@source.zip" http://localhost:8000/projects/$PROJECT_ID/codebases

# Search
curl -s -b cookies.txt -X POST http://localhost:8000/projects/$PROJECT_ID/search \
  -H "Content-Type: application/json" -d '{"query":"mobile OTP verification","content_type":"all"}'
```

Both uploads should report `"status":"ready"`; search should return ranked results with plausible
similarity scores and the correct `content_type` for each filter.

### Verifying the agent workflow

Requires a free [Gemini](https://aistudio.google.com/apikey) API key set as `GEMINI_API_KEY` in `.env`. With
requirements/code already uploaded to `$PROJECT_ID` above:

```bash
CR=$(curl -s -b cookies.txt -X POST http://localhost:8000/projects/$PROJECT_ID/requests \
  -H "Content-Type: application/json" \
  -d '{"request_text":"Make mobile OTP verification mandatory before a loan application can proceed."}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

RUN=$(curl -s -b cookies.txt -X POST http://localhost:8000/requests/$CR/analyse)
echo "$RUN"   # status is one of: awaiting_clarification | awaiting_approval | failed

# If awaiting_clarification, answer it (use the run's "id" from $RUN):
curl -s -b cookies.txt -X POST http://localhost:8000/runs/<run_id>/clarification \
  -H "Content-Type: application/json" -d '{"answer":"Trigger OTP at final submission."}'

# Once awaiting_approval, approve it (use the run's "plan_id"):
curl -s -b cookies.txt -X POST http://localhost:8000/plans/<plan_id>/decision \
  -H "Content-Type: application/json" -d '{"decision":"approved"}'
```

Expect: a real classification, evidence cited from your uploaded documents/code, a generated user
story with acceptance criteria and test cases, and citations that only ever reference chunk ids and
file paths that genuinely appeared in this run's search results (enforced by a deterministic
grounding check, not the model's self-report).

### 3. Frontend (`apps/web`)

```bash
cd apps/web
npm install
cp .env.example .env.local       # NEXT_PUBLIC_API_URL defaults to http://localhost:8000
npm run dev                      # http://localhost:3000
```

Open [http://localhost:3000](http://localhost:3000) — it redirects to `/sign-in`. Register an account,
then create a project from the dashboard.

## Environment variables

**`apps/api/.env`**

| Variable                      | Purpose                                                         |
| ------------------------------ | ---------------------------------------------------------------- |
| `DATABASE_URL`                 | Postgres connection string (Neon/Supabase)                      |
| `JWT_SECRET`                   | Signing secret for session cookies                               |
| `JWT_ALGORITHM`                | JWT signing algorithm (default `HS256`)                          |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | Session lifetime in minutes                                      |
| `FRONTEND_ORIGIN`               | Origin allowed by CORS (the Next.js dev/prod URL)                |
| `GEMINI_API_KEY`               | Gemini API key — powers classification, tool selection, and plan generation |
| `GEMINI_MODEL_NAME`            | Gemini model for the agent (default `gemini-3.5-flash-lite`)       |
| `AGENT_MAX_STEPS`              | Cap on tool-calling turns before forcing an insufficient-evidence fallback |
| `AGENT_REVIEW_MAX_RETRIES`     | How many times a plan can be bounced back for ungrounded citations before falling back |
| `EMBEDDING_MODEL_NAME`         | sentence-transformers model used to embed chunks (default `all-MiniLM-L6-v2`) |
| `EMBEDDING_DIMENSIONS`        | Must match the model's output dimension (384 for the default)    |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Character-based chunking window for requirement docs and code    |
| `MAX_DOCUMENT_SIZE_MB`         | Upload size limit for requirement documents                       |
| `MAX_ZIP_FILES` / `MAX_ZIP_UNCOMPRESSED_MB` | Safety limits on uploaded code archives              |
| `GITHUB_IMPORT_MAX_DOWNLOAD_MB` | Size cap on a repo ZIP downloaded via GitHub import (default 50)  |
| `MIN_RELEVANCE_SCORE`          | Minimum cosine similarity for a search result to be returned      |

**`apps/web/.env.local`**

| Variable              | Purpose                          |
| ---------------------- | --------------------------------- |
| `NEXT_PUBLIC_API_URL`  | Base URL of the FastAPI backend  |

## Data model

- `users` — email, password hash, role (`contributor` / `reviewer` / `administrator`), created_at
- `projects` — name, owner, created_at
- `project_members` — project ↔ user membership, used to isolate project data
- `documents` — project, filename, kind (`requirement` / `code`), processing status, error
- `content_chunks` — project, document, content type, text, `pgvector` embedding, source metadata
  (page number for requirement chunks; file path/symbol/line range for code chunks)
- `change_requests` — project, requester, request text, classification, status
- `agent_runs` — change request, LangGraph checkpointer thread id, status, timestamps
- `agent_steps` — run, tool name, input/output summary, status (the visible execution timeline)
- `generated_plans` — change request, run, version, the full structured plan (JSON)
- `approvals` — plan, reviewer, decision, feedback, final content (for edit-approve)

LangGraph's own checkpointer (`langgraph-checkpoint-postgres`) manages a separate set of tables
(`checkpoints`, `checkpoint_writes`, ...) in the same database, created via its own `.setup()` call
the first time it runs rather than an Alembic migration.

See [`docs/database-schema.md`](docs/database-schema.md) for full column/index detail and the
migration history, and [`docs/architecture.md`](docs/architecture.md) for a system diagram and the
agent's state-machine flow. [`docs/api.md`](docs/api.md) documents every endpoint with examples.

## Deployment

Config for both hosting paths the BRD recommends is checked in - none of it has been pointed at a
live paid account, so this is "ready to deploy", not "currently deployed":

- **Local, one command:** `docker-compose up --build` from the repo root (after copying
  `apps/api/.env.example` → `apps/api/.env` with a real `GEMINI_API_KEY`) starts Postgres+pgvector,
  the API, and the web app together - `http://localhost:3000` / `http://localhost:8000`.
- **Frontend → Vercel:** import the repo, set the project's root directory to `apps/web`
  (`vercel.json` is already there), and set `NEXT_PUBLIC_API_URL` to the deployed API's URL.
- **Frontend → Cloudflare (alternative to Vercel):** the frontend can't run on Cloudflare's own
  Workers as plain Next.js - it goes through [OpenNext](https://opennext.js.org/cloudflare), which
  compiles it to something Cloudflare's edge runtime can run. Already wired up in `apps/web`:
  `open-next.config.ts`, `wrangler.jsonc`, and two scripts. One-time setup: `npx wrangler login`
  (opens a browser to authorize your Cloudflare account - only you can do this, it's tied to your
  account). Then, from `apps/web`:
  ```bash
  NEXT_PUBLIC_API_URL=https://your-deployed-api-url npm run cf:deploy
  ```
  `NEXT_PUBLIC_API_URL` must be set in the shell *before* this command (or in
  `apps/web/.env.production`) - Next.js bakes `NEXT_PUBLIC_*` vars into the client bundle at build
  time, so setting it as a Cloudflare dashboard/Workers variable afterward has no effect. Use
  `npm run cf:preview` first to test locally against Cloudflare's runtime (via `workerd`) before
  deploying for real. The backend still can't run on Cloudflare (no support for a long-running
  Python process with `sentence-transformers`/`psycopg`/etc.) - pair this with the Render setup
  below, or any other Python host.
- **API → a Python host (Render):** `apps/api/render.yaml` is a ready-to-use Render Blueprint
  (`apps/api/Dockerfile` runs `alembic upgrade head` then `uvicorn` on start) - set the
  `DATABASE_URL`, `JWT_SECRET`, `FRONTEND_ORIGIN`, and `GEMINI_API_KEY` secrets in the Render
  dashboard. Any other Docker-friendly host works the same way (Fly.io, Railway, a VM).
- **Database:** the existing free-tier Neon/Supabase Postgres already in use for development works
  unchanged in production - just point `DATABASE_URL` at it.
