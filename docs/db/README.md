# DB Reference

PostgreSQL is the durable source of truth for NutriAgent. Redis is used only for Celery queues, live progress, and short TTL caches. Frontend `localStorage` stores only client session hints such as token, task id, plan id, and draft form state.

Files:

- `schema.sql` - compact target schema overview for the normalized PostgreSQL model.
- `triggers.sql` - PostgreSQL trigger functions used by migrations.
- `queries-simple.sql` - 10 simple queries.
- `queries-complex.sql` - 10 reporting/analytical queries.
- `roles.sql` - role and permission sketch.

Alembic remains the executable migration source. These SQL files are reference material for reviewing the final DB shape; do not edit production schema directly from this folder.
