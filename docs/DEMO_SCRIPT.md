# Recorded demo script (60–90 seconds)

Use this as a Loom / screen-recording outline for hiring managers.

## Setup before recording

```bash
cd backend
source .venv/bin/activate
python -m app.tasks.seed_demo_data
# optional live motion:
# LIVE_INGEST=1 uvicorn ...   OR   python -m app.tasks.generate_live_demo
```

Open the dashboard (local `http://localhost:5173` or your Render URL).

## Shot list

1. **Overview (10s)** — KPIs + Source mix (rss / reddit / cisa / nvd / synthetic).
2. **Alerts (20s)** — Open a high/critical alert; show score, why-flagged, evidence (+ CVEs if present).
3. **Organizations → Org Detail (25s)** — Select Acme Logistics (or top-risk org). Show **Risk brief**: level, 24h vs baseline, narratives, evidence, caveats.
4. **Org Trend (10s)** — Mention volume spike on the chart.
5. **Narratives (15s)** — Cluster title, keywords, rule-based summary, top posts.
6. **Close (10s)** — “Explainable signals over black-box AI; public/synthetic data; deployable via Render.”

## Talking points

- Detection path is deterministic (keywords, volume windows, TF-IDF clusters).
- SSE + polling keep the dashboard fresh without replacing REST APIs.
- CISA/NVD/Reddit are official public sources — no unsupported scraping.
- Risk brief is analyst-oriented: volume ratio, evidence links, explicit caveats.

## Optional B-roll

- Terminal: `POST /api/ingest/run` or `generate_live_demo` while Overview/Alerts refresh.
- API docs: `http://localhost:8000/docs` → `/organizations/{slug}/risk-brief`.
