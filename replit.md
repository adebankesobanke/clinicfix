# ClinicFix

ClinicFix is a beginner-friendly Flask REST API for clinic equipment, maintenance staff, and maintenance requests.

## Run & Operate

- `uv sync --dev` — install Python dependencies
- `cd artifacts/api-server && uv run --project ../.. python -m clinicfix` — run the API server
- `cd artifacts/api-server && uv run --project ../.. pytest` — run automated tests
- Set `DATABASE_URL` to a PostgreSQL connection URL to use PostgreSQL; local development uses SQLite if it is not set.
- API routes are under `/api`; `GET /api/healthz` checks that the server is up.

## Stack

- Python 3.11+
- API: Flask
- ORM: SQLAlchemy via Flask-SQLAlchemy
- Database: PostgreSQL with psycopg; SQLite fallback for local development and tests
- Tests: pytest

## Where things live

- `artifacts/api-server/clinicfix/` — Flask app, models, validation, routes, and entry point
- `artifacts/api-server/tests/` — API tests
- `README.md` — setup guide and endpoint examples

## Architecture decisions

- The service uses PostgreSQL when `DATABASE_URL` is configured and SQLite for a zero-configuration local start.
- The API creates its tables at startup to keep the first version easy to run; use migrations before evolving a production schema.

## Product

- Create, list, retrieve, update, and delete equipment, maintenance staff, and maintenance requests.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The shared API service receives requests at `/api`; keep that prefix on all endpoints.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
