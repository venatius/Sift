---
name: sift-db-migration
description: Design or review data-preserving SQLite schema migrations in Sift.
---

# Sift database migrations

Use for Sift SQLite schema changes. Preserve existing records and make migrations safe to run repeatedly.

- Back up a copy of the old database before migration work; never experiment on the user's real database.
- Enable foreign keys on each connection and keep them enabled during migration.
- Create new tables and indexes with `IF NOT EXISTS`.
- Before each `ALTER TABLE`, inspect `PRAGMA table_info(table)` and add only missing columns.
- Make migration steps idempotent and preserve the supported `user_version` contract.
- Test twice on a throwaway copy of an old-version database. Check that Phase 1/2 records survive, foreign keys remain enabled, and the resulting schema/version are correct.
- Report backup location, source schema, migration outcome, and test evidence. Do not commit unless asked.
