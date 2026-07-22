# Cyber Narrative Radar

Cyber Narrative Radar is a portfolio-grade cybersecurity self-starter project inspired by the public concept behind narrative-intelligence platforms such as Narravance and ChatterFlow, but adapted for cybersecurity early warning rather than trading.

## Goal

Build a local-first MVP that:

- Ingests public cyber-related text data from safe sources such as RSS, Reddit, and synthetic chatter.
- Normalizes and enriches those records.
- Maps content to organizations, sectors, and cyber narrative categories.
- Detects unusual spikes and shifts in discussion.
- Creates explainable alerts with evidence.
- Displays alerts and drilldowns in a simple analyst dashboard.

## Why this project matters

This project demonstrates:

- Cybersecurity reasoning
- Applied NLP
- OSINT-style analysis
- Product thinking
- Dashboard design
- Explainable AI-assisted workflows

## MVP categories

- Data breach
- Ransomware
- Phishing / social engineering
- Zero-day / critical vulnerability
- Supply chain compromise
- Deepfake / disinformation cyber influence

## Proposed stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Celery

### Analytics
- pandas
- scikit-learn
- sentence-transformers
- spaCy

### Frontend
- React
- TypeScript
- Tailwind CSS
- Recharts

### Local development
- Docker Compose

## Repo structure

```text
cyber-narrative-radar/
  backend/
    app/
      api/
      collectors/
      analytics/
      services/
      db/
      tasks/
      schemas/
    tests/
    requirements.txt
    Dockerfile
  frontend/
    src/
      components/
      pages/
      lib/
    package.json
    Dockerfile
  obsidian/
    Cyber Narrative Radar/
      00 Home.md
      01 Vision.md
      02 Architecture.md
      03 Data Sources.md
      04 Threat Taxonomy.md
      05 MVP Roadmap.md
      06 Portfolio Story.md
      Mind Map.md
  docker-compose.yml
  README.md
  AGENTS.md
  .cursor/
    rules/
      project.mdc
      python.mdc
      typescript.mdc
```

## MVP workflow

Sources -> Ingestion -> Normalization -> Storage -> Analytics -> Alerts -> Dashboard

## Phase plan

### Phase 1
- Scaffold backend and frontend
- Create Docker Compose
- Add placeholder API routes
- Add placeholder frontend pages
- Add Obsidian notes

### Phase 2
- Add models and schemas
- Add Alembic migration
- Add sample seed data

### Phase 3
- Implement ingestion
- Add RSS connector
- Add Reddit connector if feasible
- Add synthetic chatter generator

### Phase 4
- Implement analytics
- Add threat tagging
- Add entity mapping
- Add anomaly scoring
- Add explainable alerts

### Phase 5
- Build dashboard pages
- Add charts and drilldowns

### Phase 6
- Add optional LLM summaries outside the critical detection path

## Deployment

### Option A — Render (full stack blueprint)

Use the root `render.yaml` Blueprint to deploy both services:

1. Push this repo to GitHub/GitLab.
2. In Render: **New → Blueprint** and select the repo.
3. Render creates:
   - `cyber-narrative-radar-api` — FastAPI (`backend/`, uvicorn)
   - `cyber-narrative-radar-web` — Vite static site (`frontend/dist`)
4. Blueprint wiring:
   - Backend `FRONTEND_URL` ← frontend public URL (CORS)
   - Frontend `VITE_API_BASE_URL` ← API public URL (baked at build time)

After deploy, open the static site URL and confirm `/api/health` on the API service.

Optional: replace the default SQLite `DATABASE_URL` with Render Postgres in the API service settings for durable storage.

### Option B — Railway backend (stronger API option)

Railway is a strong choice when you want a containerized API with a durable disk or managed Postgres, then host the frontend separately (Render static, Netlify, Cloudflare Pages, etc.).

1. Create a Railway project from this repo.
2. Set the service root / Dockerfile path to `backend/` (uses `backend/Dockerfile`).
3. Configure env vars:
   - `FRONTEND_URL` — your deployed dashboard origin
   - `DATABASE_URL` — Railway Postgres connection string (recommended) or SQLite
   - `ENVIRONMENT=production`
4. Deploy; Railway sets `PORT` automatically (the Dockerfile already respects it).
5. Build the frontend with the Railway API URL:

```bash
cd frontend
cp .env.example .env
# set VITE_API_BASE_URL=https://your-railway-api.up.railway.app
npm install && npm run build
```

Serve `frontend/dist` on any static host, and keep `FRONTEND_URL` on the API pointed at that host.

### Useful env vars

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | Backend | SQLite locally; Postgres in production |
| `FRONTEND_URL` | Backend | CORS allowlist for the dashboard |
| `VITE_API_BASE_URL` | Frontend build | API origin baked into the client |
| `ENVIRONMENT` | Backend | `local` or `production` |

## Demo checklist

- [ ] Backend healthy: `GET /api/health` returns `healthy`
- [ ] Seed or ingest data (local): `python -m app.tasks.seed_demo_data` then optional `ingest_rss` / `score_posts`
- [ ] Alerts page loads with scores, evidence, search, and filters
- [ ] Organizations: search/sector filters work; selecting an org updates Detail + Trend
- [ ] Narratives: clusters show title, count, summary, orgs/categories, top posts
- [ ] Overview KPIs and charts (categories / volume) render without console errors
- [ ] CORS works between deployed frontend and API (`FRONTEND_URL` / `VITE_API_BASE_URL` set)
- [ ] Portfolio walkthrough ready: alert → org drilldown → narrative cluster explainability
