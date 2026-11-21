-- EventSphere final Neon/PostgreSQL migration draft - v2.
--
-- This file is advisory and has not been executed.
-- It is intended for manual DBA review and a low-traffic maintenance window.
--
-- This migration:
-- - preserves all existing data;
-- - does not recreate or drop tables;
-- - does not update business records;
-- - aborts if required schema prerequisites or clean uniqueness are absent;
-- - detects existing foreign keys by referenced table and columns;
-- - detects existing semantic unique indexes, not just index names;
-- - uses concurrent indexes where possible to reduce write blocking;
-- - adds the checked_in_by foreign key NOT VALID, then validates it.
--
-- Migration v2 deliberately does not change waitlist status constraints.
-- database/migrations/001_waitlist_idempotency.sql must be reviewed and
-- applied first, before this file, on an existing database.

-- ---------------------------------------------------------------------------
-- 1. Required table and column preflight
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    missing text;
BEGIN
    WITH required(table_name, column_name) AS (
        VALUES
            ('users', 'id'),
            ('users', 'role'),
            ('user_sessions', 'user_id'),
            ('user_sessions', 'token_hash'),
            ('events', 'id'),
            ('events', 'created_by'),
            ('events', 'status'),
            ('events', 'start_time'),
            ('ticket_categories', 'id'),
            ('ticket_categories', 'event_id'),
            ('bookings', 'id'),
            ('bookings', 'user_id'),
            ('bookings', 'event_id'),
            ('bookings', 'status'),
            ('payments', 'id'),
            ('payments', 'booking_id'),
            ('waitlist', 'id'),
            ('waitlist', 'user_id'),
            ('waitlist', 'event_id'),
            ('waitlist', 'status'),
            ('waitlist', 'created_at'),
            ('notifications', 'id'),
            ('notifications', 'user_id'),
            ('notifications', 'message'),
            ('notifications', 'is_read'),
            ('notifications', 'created_at'),
            ('tickets', 'id'),
            ('tickets', 'booking_id'),
            ('tickets', 'category_id'),
            ('tickets', 'qr_token'),
            ('tickets', 'status'),
            ('tickets', 'checked_in_at'),
            ('tickets', 'checked_in_by')
    )
    SELECT table_name || '.' || column_name
    INTO missing
    FROM required r
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = r.table_name
          AND c.column_name = r.column_name
    )
    LIMIT 1;

    IF missing IS NOT NULL THEN
        RAISE EXCEPTION
            'Required schema column is missing: %',
            missing;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. Waitlist migration prerequisites from 001_waitlist_idempotency.sql
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    waitlist_status_definition text;
    waitlist_attnum smallint;
    waitlist_id_attnum smallint;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'bookings'
          AND column_name = 'waitlist_id'
    ) THEN
        RAISE EXCEPTION
            'Prerequisite missing: bookings.waitlist_id. Apply and verify 001_waitlist_idempotency.sql first';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'bookings_waitlist_id_unique'
    ) THEN
        RAISE EXCEPTION
            'Prerequisite missing: bookings_waitlist_id_unique';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'waitlist_active_user_event_unique'
    ) THEN
        RAISE EXCEPTION
            'Prerequisite missing: waitlist_active_user_event_unique';
    END IF;

    SELECT attnum
    INTO waitlist_attnum
    FROM pg_attribute
    WHERE attrelid = 'public.bookings'::regclass
      AND attname = 'waitlist_id'
      AND NOT attisdropped;

    SELECT attnum
    INTO waitlist_id_attnum
    FROM pg_attribute
    WHERE attrelid = 'public.waitlist'::regclass
      AND attname = 'id'
      AND NOT attisdropped;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'public.bookings'::regclass
          AND c.contype = 'f'
          AND c.confrelid = 'public.waitlist'::regclass
          AND c.conkey = ARRAY[waitlist_attnum]::smallint[]
          AND c.confkey = ARRAY[waitlist_id_attnum]::smallint[]
    ) THEN
        RAISE EXCEPTION
            'Prerequisite missing: bookings_waitlist_id_fkey';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO waitlist_status_definition
    FROM pg_constraint c
    WHERE c.conrelid = 'public.waitlist'::regclass
      AND c.contype = 'c'
      AND c.conname = 'waitlist_status_check';

    IF waitlist_status_definition IS NULL
       OR waitlist_status_definition NOT ILIKE '%WAITING%'
       OR waitlist_status_definition NOT ILIKE '%OFFERED%'
       OR waitlist_status_definition NOT ILIKE '%ACCEPTED%'
       OR waitlist_status_definition NOT ILIKE '%FULFILLED%'
       OR waitlist_status_definition NOT ILIKE '%EXPIRED%'
       OR waitlist_status_definition NOT ILIKE '%CANCELLED%' THEN
        RAISE EXCEPTION
            'Prerequisite missing or invalid: waitlist_status_check';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 3. Duplicate and orphan preflight
-- ---------------------------------------------------------------------------

-- Duplicate QR tokens would make a unique index abort and would also make
-- scanner lookup ambiguous. Manual cleanup or reassignment is required.
DO $$
BEGIN
    IF EXISTS (
        SELECT qr_token
        FROM public.tickets
        WHERE qr_token IS NOT NULL
        GROUP BY qr_token
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate tickets.qr_token values exist; regenerate or reconcile them before applying this migration';
    END IF;
END
$$;

-- Existing session hashes are used for bearer-token lookup. Duplicate hashes
-- must be reconciled before adding the unique index.
DO $$
BEGIN
    IF EXISTS (
        SELECT token_hash
        FROM public.user_sessions
        WHERE token_hash IS NOT NULL
        GROUP BY token_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate user_sessions.token_hash values exist; revoke or reconcile duplicate sessions first';
    END IF;
END
$$;

-- Orphaned Gate Staff references must be reconciled before foreign-key
-- validation. Existing historical staff users should not be deleted here.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.tickets t
        LEFT JOIN public.users u ON u.id = t.checked_in_by
        WHERE t.checked_in_by IS NOT NULL
          AND u.id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Orphaned tickets.checked_in_by values exist; restore or explicitly null the references before applying';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 4. Semantic unique-index detection
-- ---------------------------------------------------------------------------
-- These checks detect uniqueness by actual indexed column and predicate,
-- rather than relying only on an index name.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_index i
        WHERE i.indrelid = 'public.tickets'::regclass
          AND i.indisunique
          AND i.indisvalid
          AND i.indnkeyatts = 1
          AND i.indpred IS NULL
          AND pg_get_indexdef(i.indexrelid, 1, true) = 'qr_token'
    ) THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'tickets'
              AND indexname = 'tickets_qr_token_unique'
        ) THEN
            RAISE EXCEPTION
                'Equivalent QR-token uniqueness exists under a different index name; keep it or rename it manually';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_index i
        WHERE i.indrelid = 'public.user_sessions'::regclass
          AND i.indisunique
          AND i.indisvalid
          AND i.indnkeyatts = 1
          AND i.indpred IS NULL
          AND pg_get_indexdef(i.indexrelid, 1, true) = 'token_hash'
    ) THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'user_sessions'
              AND indexname = 'user_sessions_token_hash_unique'
        ) THEN
            RAISE EXCEPTION
                'Equivalent session-token uniqueness exists under a different index name; keep it or rename it manually';
        END IF;
    END IF;
END
$$;

-- Named invalid-index checks are separated so concurrent index statements
-- remain outside transaction blocks and DO blocks.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = 'tickets_qr_token_unique'
          AND NOT i.indisvalid
    ) THEN
        RAISE EXCEPTION
            'tickets_qr_token_unique exists but is invalid';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'tickets'
          AND indexname = 'tickets_qr_token_unique'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_index i
        WHERE i.indrelid = 'public.tickets'::regclass
          AND i.indisunique
          AND i.indisvalid
          AND i.indnkeyatts = 1
          AND i.indpred IS NULL
          AND pg_get_indexdef(i.indexrelid, 1, true) = 'qr_token'
          AND pg_get_indexdef(i.indexrelid) LIKE '%tickets_qr_token_unique%'
    ) THEN
        RAISE EXCEPTION
            'tickets_qr_token_unique exists but has a different definition';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = 'user_sessions_token_hash_unique'
          AND NOT i.indisvalid
    ) THEN
        RAISE EXCEPTION
            'user_sessions_token_hash_unique exists but is invalid';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'user_sessions'
          AND indexname = 'user_sessions_token_hash_unique'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_index i
        WHERE i.indrelid = 'public.user_sessions'::regclass
          AND i.indisunique
          AND i.indisvalid
          AND i.indnkeyatts = 1
          AND i.indpred IS NULL
          AND pg_get_indexdef(i.indexrelid, 1, true) = 'token_hash'
          AND pg_get_indexdef(i.indexrelid) LIKE '%user_sessions_token_hash_unique%'
    ) THEN
        RAISE EXCEPTION
            'user_sessions_token_hash_unique exists but has a different definition';
    END IF;
END
$$;

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS tickets_qr_token_unique
    ON public.tickets (qr_token);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS user_sessions_token_hash_unique
    ON public.user_sessions (token_hash);

-- ---------------------------------------------------------------------------
-- 5. Supporting indexes
-- ---------------------------------------------------------------------------
-- Each index is justified by an actual application query.

-- Gate dashboard/history and ticket status/check-in reads.
CREATE INDEX CONCURRENTLY IF NOT EXISTS tickets_status_checked_in_idx
    ON public.tickets (status, checked_in_at);

-- Organiser event filtering and summary queries.
CREATE INDEX CONCURRENTLY IF NOT EXISTS events_created_by_status_idx
    ON public.events (created_by, status);

-- Published event chronological listings and reminder scans.
CREATE INDEX CONCURRENTLY IF NOT EXISTS events_status_start_time_idx
    ON public.events (status, start_time);

-- Organiser booking ownership, event, and status filtering.
CREATE INDEX CONCURRENTLY IF NOT EXISTS bookings_owner_event_status_idx
    ON public.bookings (user_id, event_id, status);

-- Latest-payment lookup for gate validation and organiser booking history.
CREATE INDEX CONCURRENTLY IF NOT EXISTS payments_booking_id_id_idx
    ON public.payments (booking_id, id DESC);

-- Notification unread counts and notification history.
CREATE INDEX CONCURRENTLY IF NOT EXISTS notifications_user_read_created_idx
    ON public.notifications (user_id, is_read, created_at DESC);

-- Waitlist FIFO processing and expiry.
CREATE INDEX CONCURRENTLY IF NOT EXISTS waitlist_fifo_idx
    ON public.waitlist (event_id, status, created_at, id);

-- ---------------------------------------------------------------------------
-- 6. Existing checked_in_by foreign-key detection
-- ---------------------------------------------------------------------------

-- Detect an FK by catalog semantics:
-- - local relation tickets;
-- - local column checked_in_by;
-- - referenced relation users;
-- - referenced column id.
-- This avoids duplicate constraints whose names differ.

DO $$
DECLARE
    checked_in_attnum smallint;
    user_id_attnum smallint;
    fk_exists boolean;
BEGIN
    SELECT attnum
    INTO checked_in_attnum
    FROM pg_attribute
    WHERE attrelid = 'public.tickets'::regclass
      AND attname = 'checked_in_by'
      AND NOT attisdropped;

    SELECT attnum
    INTO user_id_attnum
    FROM pg_attribute
    WHERE attrelid = 'public.users'::regclass
      AND attname = 'id'
      AND NOT attisdropped;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'public.tickets'::regclass
          AND c.confrelid = 'public.users'::regclass
          AND c.contype = 'f'
          AND c.conkey = ARRAY[checked_in_attnum]::smallint[]
          AND c.confkey = ARRAY[user_id_attnum]::smallint[]
    )
    INTO fk_exists;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'public.tickets'::regclass
          AND c.conname = 'tickets_checked_in_by_fkey'
    ) AND NOT fk_exists THEN
        RAISE EXCEPTION
            'tickets_checked_in_by_fkey exists but does not reference tickets.checked_in_by -> users.id';
    END IF;

    IF NOT fk_exists THEN
        -- NOT VALID avoids validating historical rows inside this ALTER.
        -- The earlier orphan preflight and the following VALIDATE make this
        -- safe, provided no concurrent orphan row is introduced between checks.
        ALTER TABLE public.tickets
            ADD CONSTRAINT tickets_checked_in_by_fkey
            FOREIGN KEY (checked_in_by)
            REFERENCES public.users(id)
            NOT VALID;
    END IF;
END
$$;

-- Validate the constraint in a separate command/phase. If an FK already
-- exists and is valid, this DO wrapper does not create or validate it again.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'public.tickets'::regclass
          AND c.conname = 'tickets_checked_in_by_fkey'
          AND NOT c.convalidated
    ) THEN
        ALTER TABLE public.tickets
            VALIDATE CONSTRAINT tickets_checked_in_by_fkey;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 7. Redundant-index review
-- ---------------------------------------------------------------------------
-- Intentionally omitted:
-- - tickets_booking_id_idx: already in schema.sql and used by ticket joins.
-- - tickets_category_id_idx: already in schema.sql and used by category joins.
-- - payments_booking_id_idx: already in schema.sql and used by payment lookup.
-- - notifications_user_created_idx: already in schema.sql.
-- - notifications_user_message_idx: omitted because no application query uses
--   message in a WHERE/filter/join predicate; it would index large text.
-- - waitlist active-name indexes: owned by migration 001 and not duplicated.

-- ---------------------------------------------------------------------------
-- Pre-migration verification SQL
-- ---------------------------------------------------------------------------
--
-- Run these read-only checks before applying v2:
--
-- SELECT current_database(), current_schema();
--
-- SELECT table_name, column_name
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND (table_name, column_name) IN (
--     ('tickets','qr_token'), ('tickets','checked_in_by'),
--     ('tickets','status'), ('tickets','checked_in_at'),
--     ('tickets','booking_id'), ('tickets','category_id'),
--     ('users','id'), ('events','created_by'), ('events','status'),
--     ('events','start_time'), ('bookings','waitlist_id'),
--     ('bookings','user_id'), ('bookings','event_id'),
--     ('payments','booking_id'), ('payments','id'),
--     ('notifications','user_id'), ('notifications','is_read'),
--     ('notifications','created_at'), ('notifications','message'),
--     ('user_sessions','token_hash'), ('waitlist','id'),
--     ('waitlist','event_id'), ('waitlist','status'),
--     ('waitlist','created_at')
--   )
-- ORDER BY table_name, column_name;
--
-- SELECT to_regclass('public.bookings_waitlist_id_unique');
-- SELECT to_regclass('public.waitlist_active_user_event_unique');
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'public.waitlist'::regclass
--   AND conname = 'waitlist_status_check';
--
-- SELECT qr_token, COUNT(*)
-- FROM public.tickets
-- WHERE qr_token IS NOT NULL
-- GROUP BY qr_token
-- HAVING COUNT(*) > 1;
--
-- SELECT token_hash, COUNT(*)
-- FROM public.user_sessions
-- WHERE token_hash IS NOT NULL
-- GROUP BY token_hash
-- HAVING COUNT(*) > 1;
--
-- SELECT COUNT(*) AS orphaned_checked_in_staff
-- FROM public.tickets t
-- LEFT JOIN public.users u ON u.id = t.checked_in_by
-- WHERE t.checked_in_by IS NOT NULL
--   AND u.id IS NULL;
--
-- SELECT c.conname, pg_get_constraintdef(c.oid)
-- FROM pg_constraint c
-- WHERE c.conrelid = 'public.tickets'::regclass
--   AND c.contype = 'f'
--   AND c.confrelid = 'public.users'::regclass;
--
-- SELECT to_regclass('public.tickets_qr_token_unique');
-- SELECT to_regclass('public.user_sessions_token_hash_unique');

-- ---------------------------------------------------------------------------
-- Post-migration verification SQL
-- ---------------------------------------------------------------------------
--
-- SELECT qr_token, COUNT(*)
-- FROM public.tickets
-- WHERE qr_token IS NOT NULL
-- GROUP BY qr_token
-- HAVING COUNT(*) > 1;
--
-- SELECT token_hash, COUNT(*)
-- FROM public.user_sessions
-- WHERE token_hash IS NOT NULL
-- GROUP BY token_hash
-- HAVING COUNT(*) > 1;
--
-- SELECT to_regclass('public.tickets_qr_token_unique');
-- SELECT to_regclass('public.user_sessions_token_hash_unique');
-- SELECT to_regclass('public.tickets_status_checked_in_idx');
-- SELECT to_regclass('public.events_created_by_status_idx');
-- SELECT to_regclass('public.events_status_start_time_idx');
-- SELECT to_regclass('public.bookings_owner_event_status_idx');
-- SELECT to_regclass('public.payments_booking_id_id_idx');
-- SELECT to_regclass('public.notifications_user_read_created_idx');
-- SELECT to_regclass('public.waitlist_fifo_idx');
--
-- SELECT c.conname, c.convalidated, pg_get_constraintdef(c.oid)
-- FROM pg_constraint c
-- WHERE c.conrelid = 'public.tickets'::regclass
--   AND c.contype = 'f'
--   AND c.confrelid = 'public.users'::regclass
--   AND pg_get_constraintdef(c.oid) ILIKE '%checked_in_by%'
--   AND pg_get_constraintdef(c.oid) ILIKE '%users%';
--
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'public.waitlist'::regclass
--   AND conname = 'waitlist_status_check';
