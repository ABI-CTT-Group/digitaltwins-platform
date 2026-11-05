-- One deployment row per build (a redeploy reuses it), and the error of a failed deploy.
-- Until now every Deploy click added a row for the same build: keep only the newest.
DELETE FROM portal.plugin_deployments d
USING portal.plugin_deployments newer
WHERE d.id <> newer.id
  AND (d.build_id = newer.build_id OR d.workflow_build_id = newer.workflow_build_id)
  AND (COALESCE(newer.created_at, '-infinity'), newer.id) > (COALESCE(d.created_at, '-infinity'), d.id);

ALTER TABLE portal.plugin_deployments ADD COLUMN IF NOT EXISTS error character varying;
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugin_deployments_build_id
    ON portal.plugin_deployments USING btree (build_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugin_deployments_workflow_build_id
    ON portal.plugin_deployments USING btree (workflow_build_id);
