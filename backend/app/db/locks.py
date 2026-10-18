"""Keys for Postgres advisory locks that serialise start-up work across instances.

The seed runs in a single transaction, so it takes a transaction-scoped lock (`pg_advisory_xact_lock`),
which also works behind a transaction-pooling PgBouncer. Migrations take a session-level lock
(`pg_advisory_lock`) because some of them commit mid-run, which would release a transaction-scoped
one; they therefore need a direct connection (MIGRATION_DATABASE_URL), not a pooler.
"""

MIGRATION_LOCK_KEY = 7_204_041_901
SEED_LOCK_KEY = 7_204_041_902
