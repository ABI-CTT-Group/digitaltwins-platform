-- Airflow deploy state of a script workflow's DAG: pending | deployed | failed (NULL for other datasets).
-- dag_error holds the reason a deploy failed. See docs/decisions/2026-10-13-deploy-script-workflow-dags.md.

ALTER TABLE public.dataset
    ADD COLUMN IF NOT EXISTS dag_status varchar(20),
    ADD COLUMN IF NOT EXISTS dag_error text;

UPDATE public.dataset SET dag_status = 'pending' WHERE workflow_type = 'script' AND dag_status IS NULL;
