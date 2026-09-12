# Spectrace AI

Agentic SDLC and codebase intelligence platform. A user uploads requirement documents and a source-code
project, submits a change request in natural language, and Spectrace AI retrieves relevant evidence from
both the documents and the codebase, proposes affected files, and generates a user story with acceptance
criteria and test cases — all grounded in cited evidence and gated behind human reviewer approval.

See [`Spectrace_AI_BRD.docx`](Spectrace_AI_BRD.docx) for the full Business Requirements Document.

## Architecture

```
Next.js (apps/web)  →  FastAPI (apps/api)  →  Postgres + pgvector (cloud: Neon or Supabase)
                                            →  Groq (LLM)               [wired in a later phase]
                                            →  sentence-transformers    [wired in a later phase]
```

| Layer          | Technology                                  |
| -------------- | -------------------------------------------- |
| Frontend       | Next.js (App Router) + TypeScript + Tailwind |
| API            | Python + FastAPI + SQLAlchemy + Alembic      |
| Database       | Postgres (Neon / Supabase free tier)         |
| Vector search  | pgvector extension on the same Postgres      |
| Agent          | LangGraph                                    |
| LLM            | Groq                                         |
| Embeddings     | sentence-transformers (local, no API key)    |

The app talks to Postgres directly through SQLAlchemy/Alembic — no vendor BaaS SDK (auth, storage
client, etc.) is used, even when the database is hosted on Supabase. This is a deliberate constraint from
the BRD to build backend engineering depth rather than depend on a managed backend platform.

## Current status

This is **Phase 1**: authentication, roles, and project CRUD — a real, runnable skeleton. Ingestion,
semantic search, and the LangGraph agent workflow are not built yet.

- [x] Monorepo scaffold, backend and frontend booting locally
- [x] User registration / login / logout (httpOnly session cookie)
- [x] Project create / list / rename / delete, isolated per user
- [ ] Requirement document ingestion (PDF/TXT/Markdown → chunks → embeddings)
- [ ] Source-code ZIP ingestion (safe-path validation → chunks → embeddings)
- [ ] Semantic search endpoints
- [ ] LangGraph agent workflow (classify → retrieve → clarify → generate plan)
- [ ] Human review workflow (approve / edit / reject / regenerate)
- [ ] Evaluation dataset and metrics
- [ ] Deployment

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

alembic upgrade head             # creates users, projects, project_members
uvicorn app.main:app --reload    # http://localhost:8000
```

Run tests (uses an in-memory SQLite DB, no cloud connection needed):

```bash
pytest
```

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
| `GROQ_API_KEY`                 | Reserved — wired in the agent-workflow phase                     |
| `EMBEDDING_MODEL_NAME`         | Reserved — sentence-transformers model, wired in ingestion phase |

**`apps/web/.env.local`**

| Variable              | Purpose                          |
| ---------------------- | --------------------------------- |
| `NEXT_PUBLIC_API_URL`  | Base URL of the FastAPI backend  |

## Data model (Phase 1)

- `users` — email, password hash, role (`contributor` / `reviewer` / `administrator`), created_at
- `projects` — name, owner, created_at
- `project_members` — project ↔ user membership, used to isolate project data

Later phases add `documents`, `content_chunks`, `change_requests`, `agent_runs`, `agent_steps`,
`generated_plans`, `approvals`, `evaluation_cases`, and `evaluation_results` (see BRD §10).
