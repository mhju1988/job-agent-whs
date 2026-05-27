-- Migration 001: Initial schema
-- Creates profile, jobs, match_scores, and applications tables.

create extension if not exists pgcrypto;  -- for gen_random_uuid()
create extension if not exists vector;    -- pgvector for embeddings

-- ---------------------------------------------------------------------------
-- profile
-- ---------------------------------------------------------------------------
create table if not exists profile (
    id          uuid primary key default gen_random_uuid(),
    summary     text,
    skills      text[],
    experience  jsonb,
    education   jsonb,
    embedding   vector(1536),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- jobs
-- ---------------------------------------------------------------------------
create table if not exists jobs (
    id          uuid primary key default gen_random_uuid(),
    source      text not null,
    external_id text not null,
    url         text not null,
    title       text not null,
    company     text,
    location    text,
    requirements text[],
    description text,
    embedding   vector(1536),
    scraped_at  timestamptz not null default now(),
    constraint jobs_source_external_id_unique unique (source, external_id)
);

create index if not exists jobs_url_idx on jobs (url);
create index if not exists jobs_scraped_at_idx on jobs (scraped_at);

create index if not exists jobs_embedding_idx
    on jobs using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- match_scores
-- ---------------------------------------------------------------------------
create table if not exists match_scores (
    id         uuid primary key default gen_random_uuid(),
    job_id     uuid not null references jobs(id) on delete cascade,
    score      double precision not null,
    gaps       text[],
    rationale  text,
    created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- applications
--
-- Per docs/legal.md §2.4, applications must survive the 90-day jobs purge.
-- The FK is therefore `on delete set null`, and we snapshot enough job
-- context (title/company/url/source) at creation time so the record stays
-- meaningful after the parent jobs row is purged.
-- ---------------------------------------------------------------------------
create table if not exists applications (
    id                uuid primary key default gen_random_uuid(),
    job_id            uuid references jobs(id) on delete set null,
    job_title         text,
    job_company       text,
    job_url           text,
    job_source        text,
    cover_letter_path text,
    cv_variant_path   text,
    status            text not null default 'new'
                          check (status in ('new','applied','interview','offer','rejected')),
    applied_at        timestamptz,
    follow_up_at      timestamptz,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);
-- Note: `updated_at` must be maintained by application code (no DB trigger yet).
