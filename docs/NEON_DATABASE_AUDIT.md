# Neon PostgreSQL Database Audit

## Scope

This audit compares `database/schema.sql`, the existing waitlist migration,
and all application SQL in `app/` and `app/agents/`. No database was connected
to, no SQL was executed, no migration was applied, and no production record
was read or changed.

## Required tables

The application requires:

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

No new table is required for organiser dashboards, payment simulation,
Gate Staff operations, or event reminders. These features reuse existing
tables and the existing Agent/Notification architecture.

## Audit findings

### Existing structures

- `users` contains registration, role, active status, and password hash fields.
- `events.created_by` supports organiser ownership.
- `tickets.checked_in_at` and `tickets.checked_in_by` support gate check-in.
- `tickets.status` supports `VALID`, `USED`, and `CANCELLED`.
- `payments.status` supports `PENDING`, `SUCCESS`, `FAILED`, and `REFUNDED`.
- `waitlist.status` supports the migration end state including `FULFILLED`.
- `notifications` supports read state and timestamps.
- `agent_messages` and `agent_states` support ACL and state persistence.

### Genuine integrity gap found

QR tokens are used to identify and validate tickets, but a fresh database
bootstrap and an existing database need a uniqueness guarantee. Duplicate
QR tokens could allow one value to match more than one ticket.

The final migration also strengthens foreign-key/index support for:

- `tickets.checked_in_by -> users.id`;
- organiser event filtering;
- booking owner/event/status filtering;
- ticket status/check-in filtering;
- notification unread and reminder duplicate lookups;
- session token lookup;
- waitlist FIFO processing.

## Migration decision

`database/migrations/neon_final_migration.sql` is required before production
deployment if the existing Neon database does not already contain these
indexes and constraints. It is additive and preserves records.

The migration will abort before change if:

- duplicate `tickets.qr_token` values exist; or
- `tickets.checked_in_by` contains orphaned user IDs.

It does not modify:

- user records;
- event records;
- bookings;
- payments;
- tickets;
- waitlist rows;
- notifications;
- agent state or agent messages.

## Manual Neon execution

1. Open a read-only transaction or the Neon SQL Editor against the intended
   deployment branch only.
2. Run the verification queries at the end of
   `database/migrations/neon_final_migration.sql` first.
3. Review and approve the migration diff.
4. Take an approved Neon backup or branch snapshot.
5. Paste the complete migration file into Neon SQL Editor.
6. Execute once.
7. Re-run the verification queries.
8. Test read-only `/health` and `/db-health` behavior after deployment.

Do not run this migration against the local `eventsphere_db` or a production
database through an automated build/deploy step.

## Verification queries

```sql
-- Duplicate QR tokens
SELECT qr_token, COUNT(*)
FROM tickets
WHERE qr_token IS NOT NULL
GROUP BY qr_token
HAVING COUNT(*) > 1;

-- Unique QR index
SELECT to_regclass('public.tickets_qr_token_unique');

-- Organiser and payment indexes
SELECT to_regclass('public.events_created_by_status_idx');
SELECT to_regclass('public.bookings_owner_event_status_idx');
SELECT to_regclass('public.payments_booking_id_idx');

-- Gate check-in fields and staff foreign key
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'tickets'::regclass
  AND conname = 'tickets_checked_in_by_fkey';

-- Notification indexes
SELECT to_regclass('public.notifications_user_read_created_idx');
SELECT to_regclass('public.notifications_user_message_idx');

-- Waitlist status constraint
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'waitlist'::regclass
  AND conname = 'waitlist_status_check';
```
