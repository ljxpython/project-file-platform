# DB Migrations

SQL migration files for PostgreSQL.

Rules:
- file name format: `NNNN_description.sql`
- files are executed in lexicographic order
- each migration is recorded in `schema_migrations`

Run manually:

```bash
uv run pfp-migrate
```
