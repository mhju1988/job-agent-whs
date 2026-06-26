-- Migration 006: extend applications.status to include 'ready_to_send'.
--
-- State semantics:
--   new           - row created (e.g. by Matcher) but no artifacts yet
--   ready_to_send - Writer Agent has produced cover_letter + cv_variant .docx;
--                   awaiting human review/click (per docs/legal.md manual-submit rule)
--   applied       - human has clicked submit on the third-party site
--   interview     - employer responded with an interview invite
--   offer         - employer extended an offer
--   rejected      - application closed unsuccessfully
begin;

alter table applications drop constraint if exists applications_status_check;
alter table applications add constraint applications_status_check
    check (status in ('new','ready_to_send','applied','interview','offer','rejected'));

commit;
