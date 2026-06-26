-- Migration 004: resize embedding columns to match multilingual-e5-large-instruct (dim 1024).
-- Destructive — drops both embedding columns + the HNSW index and recreates them.
-- Safe to run only because no rows have been inserted yet.
begin;

drop index if exists jobs_embedding_idx;
drop index if exists profile_embedding_idx;
alter table jobs    drop column if exists embedding;
alter table profile drop column if exists embedding;

alter table jobs    add column embedding vector(1024);
alter table profile add column embedding vector(1024);

create index if not exists jobs_embedding_idx
    on jobs using hnsw (embedding vector_cosine_ops);
create index if not exists profile_embedding_idx
    on profile using hnsw (embedding vector_cosine_ops);

commit;
