-- Tool datasets record their type (script / notebook / gui) so listings need not ask SEEK.
-- See docs/decisions/2026-10-01-unified-tool-dataset-ingest.md (platform repo).

ALTER TABLE public.dataset
    ADD COLUMN IF NOT EXISTS tool_type varchar(20);
