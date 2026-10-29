---
name: PostgreSQL schema safety
description: User's standing approval boundary for ClinicFix PostgreSQL schema changes.
---

For ClinicFix, do not modify the running PostgreSQL database or run a migration without explicit user approval. Do not assume `db.create_all()` adds columns to existing tables; it creates missing tables but does not update existing schemas. Propose an explicit migration and wait for approval before applying it.

**Why:** the user has repeatedly required that existing PostgreSQL data remain untouched until a migration is reviewed and approved.

**How to apply:** keep model tests on the disposable SQLite fixture, do not restart the application against a changed model before its PostgreSQL migration is applied, and never infer or backfill technician-to-staff links from names or emails.
