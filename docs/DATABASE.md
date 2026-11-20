# EventSphere Database Documentation

## Scope and evidence

This document records tables, columns, and relationships referenced by the
application SQL. The fresh-database bootstrap is provided in
`database/schema.sql`. Existing databases still require a read-only schema
comparison because the repository cannot prove their historical constraints
or data state.

All application queries use psycopg parameter binding.

## Tables and relationships

| Table | Observed columns and purpose | Relationships |
| --- | --- | --- |
| `users` | `id`, `full_name`, `email`, `password_hash`, `role`, `is_active` | Parent of sessions, bookings, venue-hire requests, waitlist entries, notifications, and check-in staff references |
| `user_sessions` | `user_id`, `token_hash`, `expires_at` | References `users`; token hashes identify active sessions |
| `venues` | `id`, `name`, `location`, `capacity`, `hourly_rate`, `private_hire_available` | Parent of events and venue-hire requests |
| `events` | `id`, `title`, `description`, `category`, `venue_id`, `start_time`, `end_time`, `status`, `created_at` | References `venues`; parent of ticket categories and bookings |
| `ticket_categories` | `id`, `event_id`, `category_name`, `price`, `quantity` | References `events`; parent of tickets |
| `bookings` | `id`, `user_id`, `event_id`, `total_amount`, `quantity`, `status`, `created_at`, and migration-added `waitlist_id` | References `users`, `events`, and optionally `waitlist` |
| `payments` | `id`, `booking_id`, `payment_reference`, `amount`, `status`, `paid_at` | References `bookings`; booking creation uses `SUCCESS`, cancellation uses `REFUNDED` |
| `tickets` | `id`, `booking_id`, `category_id`, `qr_token`, `status`, `checked_in_at`, `checked_in_by` | References `bookings`, `ticket_categories`, and the check-in staff user |
| `venue_hire_requests` | `id`, `user_id`, `venue_id`, `start_time`, `end_time`, `purpose`, `guest_count`, `quoted_price`, `status`, `created_at` | References `users` and `venues` |
| `waitlist` | `id`, `user_id`, `event_id`, `quantity`, `status`, `created_at` | References `users` and `events`; active user/event entries are unique after migration |
| `notifications` | `id`, `user_id`, `message`, `is_read`, `created_at` | References `users` |
| `agent_messages` | `id`, `sender`, `receiver`, `performative`, `content`, `conversation_id`, `created_at` | JSON message log; agent names are stored as values |
| `agent_states` | `agent_name`, `state`, `updated_at` | JSON state keyed by agent name; `agent_name` is used as the conflict key |

The exact primary-key and foreign-key constraint names should be confirmed
against the deployment database. The application assumes the referenced IDs
are relational keys and that `agent_states.agent_name` supports `ON CONFLICT`.

## Important constraints and indexes

The migration
`database/migrations/001_waitlist_idempotency.sql` defines:

1. nullable `bookings.waitlist_id` referencing `waitlist(id)`;
2. partial unique index `bookings_waitlist_id_unique` on non-null
   `waitlist_id`;
3. partial unique index `waitlist_active_user_event_unique` on
   `(user_id, event_id)` while `status = 'WAITING'`; and
4. `waitlist_status_check` preserving `WAITING`, `OFFERED`, `ACCEPTED`,
   `EXPIRED`, and `CANCELLED`, while adding `FULFILLED`.

Application logic also relies on:

- ticket categories being locked during booking;
- tickets being counted as sold when `VALID` or `USED`;
- ticket rows being locked during check-in;
- booking rows and payment rows being locked during cancellation; and
- venue rows being locked before availability and hire decisions.

## Migration safety

For a fresh Neon database, apply `database/schema.sql` once. It includes the
end state of `database/migrations/001_waitlist_idempotency.sql`; do not run
that migration a second time on the newly bootstrapped database.

There is currently one migration file. It must be reviewed against the live
database before execution because it replaces the existing
`waitlist_status_check`. A safe operational sequence is:

1. take a database backup;
2. inspect the existing constraint definition and all current waitlist status
   values; the migration aborts if unsupported values exist;
3. identify and resolve duplicate active `(user_id, event_id)` rows without
   deleting valid business data;
4. verify referenced tables and foreign keys;
5. apply the migration in a transaction;
6. verify the new indexes, constraint, and `bookings.waitlist_id`; and
7. run read-only smoke checks before enabling waitlist processing.

Do not run destructive cleanup or process production waitlist rows as part of
documentation or deployment preparation.
