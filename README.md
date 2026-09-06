# AGFinTax — Agentic Tax Coach

Reference implementation of the architecture diagram: Client (React/TS/Vite/
Tailwind) → API (FastAPI) → Guardrail → Supervisor → Agents → Tools/Services
→ Data (Postgres + pgvector, optional Redis).

## Layer → code map

| Diagram layer | Code |
|---|---|
| Client Layer | `frontend/src/components/ChatView.tsx`, `AdminKB.tsx` |
| API Layer | `backend/app/routers/*.py` |
| Guardrail Layer | `backend/app/guardrail.py` (PII regex; matches never reach the LLM) |
| Orchestration — Supervisor | `backend/app/supervisor.py` (deterministic rule-based intent router) |
| Agent Layer | `backend/app/agents/*.py` (Plan, RAG, Scenario, Life Event, Composer, Verification) |
| Tools & Services | `backend/app/tools/*.py` |
| LLM Client (ENV-configurable) | `backend/app/tools/llm_client.py` — provider/model chosen only via `LLM_PROVIDER`/`LLM_MODEL` env vars, default `claude-sonnet-4-6` |
| source_registry (DB-driven official sources) | `backend/app/models.py::SourceRegistry`, managed via `POST/PATCH/DELETE /api/kb/sources` — adding a source is a row insert, no code change |
| Data Layer | `backend/app/models.py` (SQLAlchemy models); SQLite by default, Postgres 16 + pgvector in `docker-compose.yml` |
| Audit Logger | `backend/app/audit.py` → `audit_events` table |

## Run locally (fastest path — SQLite, no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY to actually call an LLM
python -m app.seed          # demo user, tax brackets, starter source_registry rows
uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
npm run dev                 # proxies /api -> localhost:8010, see vite.config.ts
```

Open http://localhost:5173. Without `ANTHROPIC_API_KEY` set, the Composer
agent uses its deterministic fallback (built from tool results) instead of
calling an LLM, so the app is fully runnable with zero external keys.

## Run with Docker (Postgres + pgvector, Redis)

```bash
cp backend/.env.example backend/.env   # fill in ANTHROPIC_API_KEY if desired
docker compose up --build
```

Then `docker compose exec backend python -m app.seed` once to load starter data.

## Deploy a client demo to Streamlit Community Cloud (free, ~2 minutes)

`streamlit_demo/app.py` is a separate, single-file UI that calls the exact
same backend pipeline (`app.guardrail` → `app.supervisor` → `app.agents.*`
→ `app.tools.*`) directly in-process — same behavior as the FastAPI +
React app, just packaged for Streamlit's free hosting so you can hand a
client a URL.

It has its own `streamlit_demo/requirements.txt` (no `fastapi`/`uvicorn`)
because installing `streamlit` and `fastapi` in the same environment
causes a `starlette` version conflict — keep the two apps' dependencies
separate.

1. Push this repo to your GitHub.
2. Go to `share.streamlit.io` → **New app** → pick the repo → main file
   path: `streamlit_demo/app.py`.
3. Under **Advanced settings → Secrets**, add (TOML format):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   LLM_PROVIDER = "anthropic"
   LLM_MODEL = "claude-sonnet-4-6"
   ```
   (Omit `ANTHROPIC_API_KEY` to run on the deterministic fallback instead.)
4. Click **Deploy**. You'll get a `*.streamlit.app` URL to share.

Note: the demo's SQLite database resets whenever the app restarts or
redeploys — fine for a click-through demo, not for persistent client data.
For that, point `DATABASE_URL` (also settable in Secrets) at a real
Postgres instance, same as the FastAPI backend.

## Deploy it live (Render.com, free tier)

This repo includes `render.yaml`, a deploy blueprint for Render that stands
up the backend, a managed Postgres, and the static frontend together:

1. Push this repo to your own GitHub account.
2. In Render, click **New → Blueprint** and point it at the repo. Render reads
   `render.yaml` and provisions `agfintax-db` (Postgres), `agfintax-backend`
   (FastAPI), and `agfintax-frontend` (static site) automatically.
3. Once `agfintax-backend` is live, open its **Shell** tab in the Render
   dashboard and run `python -m app.seed` once, to load the demo user, tax
   brackets, and starter `source_registry` rows.
4. (Optional) Add your `ANTHROPIC_API_KEY` in the backend service's
   environment variables to get real LLM-composed answers instead of the
   deterministic fallback.
5. Open the `agfintax-frontend` URL Render gives you — that's your live,
   clickable app.

No code changes needed for any of this — `DATABASE_URL` is wired
automatically from the Postgres addon, and the frontend's `VITE_API_BASE`
points at the backend service by name.

## Or run it live in 60 seconds, locally

```bash
cp backend/.env.example backend/.env   # optionally add ANTHROPIC_API_KEY
docker compose up --build
docker compose exec backend python -m app.seed
```

Open http://localhost:5173 — full click-through app, Postgres + pgvector and
Redis included, nothing else to configure.

## Adding a new official government source

No code change, no deploy — insert a row:

```bash
curl -X POST localhost:8010/api/kb/sources \
  -H 'Content-Type: application/json' \
  -d '{"domain":"hud.gov","description":"Housing programs","scope_tags":["real_estate"],"api_method":"tavily_search","enabled":true,"tier":["plus","pro"]}'
```

or use the Admin tab in the app.

## Switching LLM provider/model

Also no code change — edit `backend/.env`:

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```

To add a second provider, implement one function in
`backend/app/tools/llm_client.py` and register it in `_PROVIDERS`; no
agent, router, or Composer code needs to change.
