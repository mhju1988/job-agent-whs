-- Migration 004: add languages column to profile (Sprint 2 — Matcher Agent).
-- Wrapped in a transaction to establish the pattern for future multi-statement
-- migrations: either all statements land, or none do.
begin;

alter table profile add column if not exists languages text[];

commit;
