-- migrations/001_quota.sql
-- Run this once in the Supabase SQL editor (or via supabase CLI migrations).
-- ─────────────────────────────────────────────────────────────────────────────

-- ── api_keys ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    text        UNIQUE NOT NULL,    -- SHA-256 of the raw API key
    tier        text        NOT NULL DEFAULT 'free',  -- 'anonymous'|'free'|'pro'|'team'
    email       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- ── usage ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage (
    id          bigserial   PRIMARY KEY,
    key_hash    text        NOT NULL,
    period      text        NOT NULL,   -- 'YYYY-MM'  e.g. '2026-02'
    count       int         NOT NULL DEFAULT 0,
    UNIQUE (key_hash, period)
);

-- Index for the hot path: quota check by (key_hash, period)
CREATE INDEX IF NOT EXISTS usage_key_period ON usage (key_hash, period);

-- ── upsert_usage stored procedure ─────────────────────────────────────────────
-- Called by quota.py _increment() to atomically insert-or-increment.
CREATE OR REPLACE FUNCTION upsert_usage(p_key_hash text, p_period text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO usage (key_hash, period, count)
    VALUES (p_key_hash, p_period, 1)
    ON CONFLICT (key_hash, period)
    DO UPDATE SET count = usage.count + 1;
END;
$$;

-- ── Stripe upgrade webhook helper view ───────────────────────────────────────
-- After a Stripe payment succeeds, update the tier from 'free' → 'pro'.
-- Example:  UPDATE api_keys SET tier = 'pro' WHERE email = 'user@example.com';
