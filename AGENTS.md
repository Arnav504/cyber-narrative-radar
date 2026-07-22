# AGENTS.md

## Project

This project is a portfolio-grade cybersecurity self-starter called Cyber Narrative Radar.

## Goal

Build a local-first MVP that monitors public online discourse for emerging cybersecurity narratives affecting a watchlist of companies, sectors, or technologies. The system should detect unusual chatter, classify likely cyber narrative types, generate explainable alerts, and display them in a clean analyst dashboard.

## Users

- Cybersecurity analyst
- Risk analyst
- Policy researcher
- Security-minded strategist

## MVP Features

1. Ingest public text data from RSS, Reddit, and synthetic chatter.
2. Normalize records into a common schema.
3. Extract organizations, sectors, and threat keywords.
4. Aggregate records into time buckets.
5. Detect abnormal volume and narrative shifts.
6. Classify content into cyber narrative categories.
7. Create explainable alerts with evidence posts.
8. Expose APIs through FastAPI.
9. Show alerts and drilldowns in a React dashboard.

## Narrative Categories

- Data breach
- Ransomware
- Phishing / social engineering
- Zero-day / critical vulnerability
- Supply chain compromise
- Deepfake / disinformation cyber influence

## Constraints

- Local-first
- Public or synthetic data only
- Explainable methods over black-box systems
- LLM summaries are optional and never part of the primary detection path
- Code should be clean, modular, and easy to demo
- Avoid unsupported scraping or fabricated APIs

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Celery

### Frontend
- React
- TypeScript
- Tailwind CSS
- Recharts

### Analytics
- pandas
- scikit-learn
- sentence-transformers
- spaCy

## Architecture Principles

- Keep route files thin
- Put business logic into services and analytics modules
- Separate database models from API schemas
- Keep analytics deterministic and testable
- Prefer the simplest implementation that works locally
- Use environment variables for configuration
- Add tests for scoring, tagging, and classification logic

## Workflow For Every Task

1. Inspect current repo structure and relevant files.
2. Propose a short implementation plan.
3. Implement the smallest viable increment.
4. Add or update tests where useful.
5. Summarize changed files.
6. Explain exact local run steps.

## Non-Goals

- No HFT or trading execution features
- No brokerage integrations
- No advanced auth in MVP
- No microservices sprawl
- No unsupported scraping of private or blocked sources
- No opaque model-heavy pipeline as the core engine