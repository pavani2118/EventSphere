-- Apply only after the preflight checks documented in docs/DATABASE.md.
-- This migration does not update or delete existing business records.

BEGIN;

ALTER TABLE bookings
    ADD COLUMN IF NOT EXISTS waitlist_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'bookings'::regclass
          AND conname = 'bookings_waitlist_id_fkey'
    ) THEN
        ALTER TABLE bookings
            ADD CONSTRAINT bookings_waitlist_id_fkey
            FOREIGN KEY (waitlist_id) REFERENCES waitlist(id);
    END IF;
END
$$;

-- Fail before creating the unique index if existing active duplicates need
-- manual review. No rows are changed by this check.
DO $$
BEGIN
    IF EXISTS (
        SELECT user_id, event_id
        FROM waitlist
        WHERE status = 'WAITING'
        GROUP BY user_id, event_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate active waitlist rows exist; reconcile them before applying this migration';
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS bookings_waitlist_id_unique
    ON bookings (waitlist_id)
    WHERE waitlist_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS waitlist_active_user_event_unique
    ON waitlist (user_id, event_id)
    WHERE status = 'WAITING';

-- Preserve every existing status and add the idempotent terminal status.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM waitlist
        WHERE status NOT IN (
            'WAITING', 'OFFERED', 'ACCEPTED', 'FULFILLED',
            'EXPIRED', 'CANCELLED'
        )
    ) THEN
        RAISE EXCEPTION
            'Unsupported waitlist status exists; reconcile it before applying this migration';
    END IF;
END
$$;

ALTER TABLE waitlist
    DROP CONSTRAINT IF EXISTS waitlist_status_check;

ALTER TABLE waitlist
    ADD CONSTRAINT waitlist_status_check
    CHECK (
        status IN (
            'WAITING', 'OFFERED', 'ACCEPTED', 'FULFILLED',
            'EXPIRED', 'CANCELLED'
        )
    );

COMMIT;
