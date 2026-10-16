# ClinicFix

ClinicFix is a small REST API for tracking clinic equipment, maintenance staff, and maintenance requests. It uses Python, Flask, SQLAlchemy, and PostgreSQL.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for installing dependencies
- PostgreSQL for persistent shared data (SQLite is used automatically for a quick local start or in tests)

## Setup

From the project root:

```bash
uv sync --dev
```

To use PostgreSQL, create a database and set its connection URL before starting the API:

```bash
export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
```

If `DATABASE_URL` is not set, the API uses a local SQLite database file. Start the API from the workspace root:

```bash
cd artifacts/api-server
uv run --project ../.. python -m clinicfix
```

The server listens on port `8080` by default. Set `PORT` to use another port. The API is available under `/api`.

## Endpoints

All request bodies must be JSON. Collection endpoints return arrays; item endpoints return one object.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/healthz` | Check that the API is running |
| GET, POST | `/api/equipment` | List or create equipment |
| GET, PATCH, DELETE | `/api/equipment/{id}` | Read, update, or delete equipment |
| GET, POST | `/api/maintenance-staff` | List or create staff |
| GET, PATCH, DELETE | `/api/maintenance-staff/{id}` | Read, update, or delete staff |
| GET, POST | `/api/maintenance-requests` | List or create requests |
| GET, PATCH, DELETE | `/api/maintenance-requests/{id}` | Read, update, or delete requests |

### Example: create equipment

```bash
curl -X POST http://localhost:8080/api/equipment \
  -H "Content-Type: application/json" \
  -d '{"name":"Portable X-ray","category":"Imaging","location":"Room 3","serial_number":"XR-100"}'
```

### Example: create a maintenance request

Create equipment first, then use its returned `id`:

```bash
curl -X POST http://localhost:8080/api/maintenance-requests \
  -H "Content-Type: application/json" \
  -d '{"equipment_id":1,"description":"The power button is stuck.","priority":"high"}'
```

## Data fields

- **Equipment:** `name`, `category`, `location`, optional `serial_number`, and `status` (`active`, `maintenance`, or `retired`).
- **Maintenance staff:** `name`, `email`, optional `phone` and `specialty`, and `is_active`.
- **Maintenance request:** `equipment_id`, `description`, optional `assigned_staff_id`, `priority` (`low`, `medium`, `high`, or `urgent`), and `status` (`open`, `in_progress`, or `completed`).

On create, omitted status and priority fields use sensible defaults. Updates use `PATCH` and only change the fields provided.

## Status codes

- `200` — successful read or update
- `201` — record created
- `204` — record deleted
- `400` — invalid JSON, missing fields, or invalid field values
- `404` — route, record, or related record not found
- `405` — HTTP method not supported on a route
- `409` — duplicate unique value or a record cannot be deleted because it is still referenced

## Run tests

From the project root:

```bash
cd artifacts/api-server
uv run --project ../.. pytest
```

Tests use a temporary SQLite database and do not need a running PostgreSQL server.

## Project layout

```text
artifacts/api-server/
  clinicfix/
    __main__.py   # Local server entry point
    app.py        # Flask application setup and database configuration
    models.py     # SQLAlchemy models
    routes.py     # REST endpoints
    validation.py # JSON input validation
  tests/
    test_api.py   # Automated API tests
```

The first version creates database tables at startup to keep setup simple. For a production system with evolving schemas, add database migrations before changing existing models.
