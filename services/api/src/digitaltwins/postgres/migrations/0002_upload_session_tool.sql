-- Tool dataset upload sessions: what the commit job needs to register the tool in SEEK.
-- See docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md (platform repo).

ALTER TABLE public.upload_session
    ADD COLUMN IF NOT EXISTS tool_type       varchar(20),
    ADD COLUMN IF NOT EXISTS seek_project_id integer;
