-- EventSphere final safe Neon/PostgreSQL migration.
--
-- Purpose:
-- - Preserve all existing data.
-- - Add only integrity and query indexes that support the application.
-- - Abort if existing QR tokens are duplicated.
-- - Abort if checked_in_by contains orphaned user references before adding
--   the foreign key.
--
-- This migration does not recreate tables, delete rows, alter historical
-- records, change payment data, or change waitlist statuses.

BEGIN;

-- Preflight: QR tokens must be unique because gate validation and ticket
-- lookup use qr_token as the ticket identity.
DO $$
BEGIN
    IF EXISTS (
        SELECT qr_token
        FROM tickets
        WHERE qr_token IS NOT NULL
        GROUP BY qr_token
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate tickets.qr_token values exist; reconcile them before adding the unique index';
    END IF;
END
$$;

-- Preflight: do not add a staff foreign key if historical rows point to a
-- deleted or unknown user.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM tickets t
        LEFT JOIN users u ON u.id = t.checked_in_by
        WHERE t.checked_in_by IS NOT NULL
          AND u.id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Orphaned tickets.checked_in_by values exist; reconcile them before adding the foreign key';
    END IF;
END
$$;

-- Gate and QR lookups.
CREATE UNIQUE INDEX IF NOT EXISTS tickets_qr_token_unique
    ON tickets (qr_token);

CREATE INDEX IF NOT EXISTS tickets_status_checked_in_idx
    ON tickets (status, checked_in_at);

CREATE INDEX IF NOT EXISTS tickets_booking_id_idx
    ON tickets (booking_id);

CREATE INDEX IF NOT EXISTS tickets_category_id_idx
    ON tickets (category_id);

-- Organiser ownership and event filtering.
CREATE INDEX IF NOT EXISTS events_created_by_status_idx
    ON events (created_by, status);

CREATE INDEX IF NOT EXISTS events_status_start_time_idx
    ON events (status, start_time);

CREATE INDEX IF NOT EXISTS bookings_owner_event_status_idx
    ON bookings (user_id, event_id, status);

-- Booking and payment history queries.
CREATE INDEX IF NOT EXISTS bookings_event_id_idx
    ON bookings (event_id);

CREATE INDEX IF NOT EXISTS bookings_user_id_idx
    ON bookings (user_id);

CREATE INDEX IF NOT EXISTS payments_booking_id_idx
    ON payments (booking_id);

-- Notification unread counts and reminder duplicate checks.
CREATE INDEX IF NOT EXISTS notifications_user_created_idx
    ON notifications (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS notifications_user_read_created_idx
    ON notifications (user_id, is_read, created_at DESC);

CREATE INDEX IF NOT EXISTS notifications_user_message_idx
    ON notifications (user_id, message);

-- Session validation and active waitlist/event queries.
CREATE INDEX IF NOT EXISTS user_sessions_user_id_idx
    ON user_sessions (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS user_sessions_token_hash_unique
    ON user_sessions (token_hash);

CREATE INDEX IF NOT EXISTS waitlist_fifo_idx
    ON waitlist (event_id, status, created_at, id);

-- Ensure the existing ticket check-in staff column has a foreign key.
-- The name is explicit so verification is straightforward.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'tickets'::regclass
          AND conname = 'tickets_checked_in_by_fkey'
    ) THEN
        ALTER TABLE tickets
            ADD CONSTRAINT tickets_checked_in_by_fkey
            FOREIGN KEY (checked_in_by) REFERENCES users(id);
    END IF;
END
$$;

COMMIT;

-- Verification queries (run read-only after the migration):
--
-- SELECT qr_token, COUNT(*) FROM tickets
-- WHERE qr_token IS NOT NULL GROUP BY qr_token HAVING COUNT(*) > 1;
--
-- SELECT to_regclass('public.tickets_qr_token_unique');
-- SELECT to_regclass('public.events_created_by_status_idx');
-- SELECT to_regclass('public.bookings_owner_event_status_idx');
-- SELECT to_regclass('public.notifications_user_read_created_idx');
-- SELECT to_regclass('public.notifications_user_message_idx');
--
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'tickets'::regclass
--   AND conname = 'tickets_checked_in_by_fkey';
--
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'waitlist'::regclass
--   AND conname = 'waitlist_status_check';
