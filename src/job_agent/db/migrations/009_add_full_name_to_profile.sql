-- Add full_name to profile table.
-- Nullable so existing rows (and re-parses where the LLM omits the field) survive.
alter table profile
    add column if not exists full_name text;
