# Neon Schema Setup

`database/schema.sql` is the bootstrap schema for a **fresh** EventSphere
PostgreSQL database. It is generated from the SQL statements in the
application and includes the end state of
`database/migrations/001_waitlist_idempotency.sql`.

## Required tables

The schema creates these 13 tables:

1. `users`
2. `user_sessions`
3. `venues`
4. `events`
5. `ticket_categories`
6. `waitlist`
7. `bookings`
8. `payments`
9. `tickets`
10. `venue_hire_requests`
11. `notifications`
12. `agent_messages`
13. `agent_states`

## Fresh Neon database procedure

1. Create a new Neon database or branch dedicated to EventSphere.
2. Confirm the selected database is the intended fresh target.
3. Open the Neon SQL Editor for that target database.
4. Paste the complete contents of `database/schema.sql`.
5. Review the SQL before execution.
6. Execute it once.
7. Verify the 13 tables and the following required objects:
   - `users_email_unique`;
   - `user_sessions_token_hash_unique`;
   - `bookings_waitlist_id_unique`;
   - `waitlist_active_user_event_unique`;
   - `waitlist_status_check`; and
   - the foreign-key constraints declared in the file.
8. Configure Vercel with the Neon connection variables and
   `PGSSLMODE=require`.
9. Test `/db-health`, registration, login, and a read-only event request.

Do not paste passwords or connection strings into source control, chat,
screenshots, or public logs.

## Existing or non-empty database

Do **not** run `database/schema.sql` against an existing database. It is not a
data-preserving migration and does not contain reconciliation logic for
pre-existing objects or rows.

For an existing EventSphere database:

1. Take an approved backup.
2. Inspect the current tables, columns, constraints, indexes, and status
   values.
3. Compare them with `database/schema.sql`.
4. Apply only reviewed, additive migration statements.
5. Apply `database/migrations/001_waitlist_idempotency.sql` only after its
   documented duplicate and status preflight checks pass.

Never run either file against the original local `eventsphere_db` for this
deployment task. The schema files do not connect to a database automatically.

## Evidence and known limitations

The application source proves the columns used by its queries and the
waitlist migration proves the waitlist idempotency objects. The source does
not prove historical constraint names or every previous production column.
The bootstrap file therefore defines a coherent fresh database, while an
existing database still requires schema inspection before migration.

The application does not automatically create tables or run migrations during
startup, build, or request handling.
