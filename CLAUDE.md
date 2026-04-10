# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based options (financial) API. The project uses SQLAlchemy for persistence, APScheduler for scheduled jobs, and structlog for structured logging.

## Commands

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the server

```bash
uvicorn app.main:app --reload
```

### Run tests

```bash
pytest                          # all tests
pytest path/to/test_file.py     # single file
pytest -k "test_name"           # single test by name
```

## Architecture

The app follows a layered FastAPI structure under `app/`:

- `main.py` — FastAPI app instantiation, router registration, lifespan events
- `api/` — Route handlers (thin layer; delegate to services)
- `services/` — Business logic; this is where most computation lives
- `models/` — SQLAlchemy ORM models (database schema)
- `schemas/` — Pydantic request/response schemas (API surface)
- `core/config.py` — Settings via `pydantic-settings` (reads from `.env`)
- `core/database.py` — SQLAlchemy engine/session factory

### Data flow

Request → `api/` router → `services/` → `models/` (SQLAlchemy) → DB

Pydantic `schemas/` are used for request validation and response serialization; they are kept separate from SQLAlchemy `models/`.

### Key dependencies

| Package | Role |
|---|---|
| `fastapi` / `uvicorn` | Web framework and ASGI server |
| `sqlalchemy` | ORM / database access |
| `pydantic-settings` | Config management from env vars |
| `apscheduler` | Background/scheduled jobs |
| `structlog` | Structured JSON logging |
| `httpx` | Async HTTP client for external calls |
| `pytest-asyncio` | Async test support |

### Environment

Configuration is loaded via `pydantic-settings` from a `.env` file (excluded from git). Copy any required vars into a local `.env` before running.
