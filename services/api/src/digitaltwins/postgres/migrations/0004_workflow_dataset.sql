-- Workflow datasets: their type (script / notebook / gui) and the tool dataset each step runs.
-- A workflow definition is a dataset with workflow_type set; the "workflows" category is shared
-- with assay workspace outputs. See docs/decisions/2026-10-02-workflow-dataset-ingest.md (platform repo).

ALTER TABLE public.dataset
    ADD COLUMN IF NOT EXISTS workflow_type varchar(20);

ALTER TABLE public.upload_session
    ADD COLUMN IF NOT EXISTS workflow_type varchar(20);

CREATE TABLE IF NOT EXISTS public.workflow_tool (
    workflow_dataset_uuid uuid NOT NULL REFERENCES public.dataset (dataset_uuid) ON DELETE CASCADE,
    step_id               varchar(255) NOT NULL,
    -- No cascade: a tool that a workflow still uses cannot be deleted on its own.
    tool_dataset_uuid     uuid NOT NULL REFERENCES public.dataset (dataset_uuid),
    PRIMARY KEY (workflow_dataset_uuid, step_id)
);

CREATE INDEX IF NOT EXISTS workflow_tool_tool_idx ON public.workflow_tool (tool_dataset_uuid);
