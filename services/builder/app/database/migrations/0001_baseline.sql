-- The portal schema as of 2026-10-21, and the catch-up for portal schemas the builder created earlier.
-- docs/decisions/2026-10-21-builder-numbered-sql-migrations.md
--
-- Until this migration, the builder's startup ran create_all and then hand-written catch-up code on
-- every start, with no record of what had run. The portal tables have been in Postgres since
-- 2026-09-28 (commit bf7a3325), so a schema may be in any shape from then on. Every statement here is
-- idempotent: on an empty schema it creates everything; on an older one it adds only what is missing.
-- Tables the models no longer define (measurements, measurement_annotations) are left alone.

-- Types ---------------------------------------------------------------------------------------------

DO $$
BEGIN
    CREATE TYPE portal.plugin_label AS ENUM ('GUI', 'Script', 'Notebook');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
ALTER TYPE portal.plugin_label ADD VALUE IF NOT EXISTS 'Notebook';

-- Tables, as create_all builds them -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS portal.plugins (
    id character varying NOT NULL,
    uuid character varying,
    name character varying NOT NULL,
    version character varying NOT NULL,
    description text,
    author character varying,
    repository_url character varying NOT NULL,
    source_type character varying NOT NULL,
    local_archive_path character varying,
    plugin_metadata json,
    label portal.plugin_label NOT NULL,
    has_backend boolean NOT NULL,
    frontend_folder character varying NOT NULL,
    frontend_build_command character varying NOT NULL,
    backend_folder character varying,
    backend_deploy_command character varying,
    seek_project_id integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT plugins_pkey PRIMARY KEY (id),
    CONSTRAINT plugins_uuid_key UNIQUE (uuid)
);
CREATE INDEX IF NOT EXISTS ix_plugins_id ON portal.plugins USING btree (id);
CREATE INDEX IF NOT EXISTS ix_plugins_name ON portal.plugins USING btree (name);

CREATE TABLE IF NOT EXISTS portal.workflows (
    id character varying NOT NULL,
    uuid character varying,
    name character varying NOT NULL,
    version character varying NOT NULL,
    description text,
    author character varying,
    repository_url character varying NOT NULL,
    source_type character varying NOT NULL,
    local_archive_path character varying,
    workflow_type character varying,
    is_sds boolean,
    seek_project_id integer,
    has_backend boolean,
    frontend_folder character varying,
    frontend_build_command character varying,
    backend_folder character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT workflows_pkey PRIMARY KEY (id),
    CONSTRAINT workflows_uuid_key UNIQUE (uuid)
);
CREATE INDEX IF NOT EXISTS ix_workflows_id ON portal.workflows USING btree (id);
CREATE INDEX IF NOT EXISTS ix_workflows_name ON portal.workflows USING btree (name);

CREATE TABLE IF NOT EXISTS portal.plugin_builds (
    id character varying NOT NULL,
    plugin_id character varying NOT NULL,
    build_id character varying NOT NULL,
    status character varying NOT NULL,
    build_logs text,
    error_messages text,
    s3_path character varying,
    expose_name character varying,
    dataset_path character varying,
    handoff_status character varying,
    upload_id character varying,
    dataset_uuid character varying,
    seek_id character varying,
    handoff_error text,
    handoff_user character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT plugin_builds_pkey PRIMARY KEY (id),
    CONSTRAINT plugin_builds_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugin_builds_build_id ON portal.plugin_builds USING btree (build_id);
CREATE INDEX IF NOT EXISTS ix_plugin_builds_id ON portal.plugin_builds USING btree (id);

CREATE TABLE IF NOT EXISTS portal.workflow_builds (
    id character varying NOT NULL,
    workflow_id character varying NOT NULL,
    build_id character varying NOT NULL,
    status character varying NOT NULL,
    build_logs text,
    error_messages text,
    s3_path character varying,
    expose_name character varying,
    dataset_path character varying,
    handoff_status character varying,
    upload_id character varying,
    dataset_uuid character varying,
    seek_id character varying,
    handoff_error text,
    handoff_user character varying,
    tool_name character varying,
    bundle_path character varying,
    tool_dataset_uuid character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT workflow_builds_pkey PRIMARY KEY (id),
    CONSTRAINT workflow_builds_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_workflow_builds_build_id ON portal.workflow_builds USING btree (build_id);
CREATE INDEX IF NOT EXISTS ix_workflow_builds_id ON portal.workflow_builds USING btree (id);

CREATE TABLE IF NOT EXISTS portal.plugin_deployments (
    id character varying NOT NULL,
    plugin_id character varying,
    build_id character varying,
    workflow_build_id character varying,
    deploy_id character varying NOT NULL,
    status character varying NOT NULL,
    source_path character varying,
    up boolean,
    route_prefix character varying,
    internal_host character varying,
    internal_port character varying,
    has_websocket boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT plugin_deployments_pkey PRIMARY KEY (id),
    CONSTRAINT ck_plugin_deployments_one_build CHECK (((build_id IS NULL) <> (workflow_build_id IS NULL))),
    CONSTRAINT plugin_deployments_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id),
    CONSTRAINT plugin_deployments_build_id_fkey FOREIGN KEY (build_id) REFERENCES portal.plugin_builds(build_id),
    CONSTRAINT plugin_deployments_workflow_build_id_fkey
        FOREIGN KEY (workflow_build_id) REFERENCES portal.workflow_builds(build_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugin_deployments_deploy_id ON portal.plugin_deployments USING btree (deploy_id);
CREATE INDEX IF NOT EXISTS ix_plugin_deployments_id ON portal.plugin_deployments USING btree (id);

CREATE TABLE IF NOT EXISTS portal.plugin_annotations (
    id character varying NOT NULL,
    plugin_id character varying NOT NULL,
    annotation_id character varying NOT NULL,
    sparc_note character varying,
    fhir_note character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT plugin_annotations_pkey PRIMARY KEY (id),
    CONSTRAINT plugin_annotations_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugin_annotations_annotation_id ON portal.plugin_annotations USING btree (annotation_id);
CREATE INDEX IF NOT EXISTS ix_plugin_annotations_id ON portal.plugin_annotations USING btree (id);

CREATE TABLE IF NOT EXISTS portal.workflow_annotations (
    id character varying NOT NULL,
    workflow_id character varying NOT NULL,
    annotation_id character varying NOT NULL,
    fhir_note character varying,
    sparc_note character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT workflow_annotations_pkey PRIMARY KEY (id),
    CONSTRAINT workflow_annotations_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_workflow_annotations_annotation_id ON portal.workflow_annotations USING btree (annotation_id);
CREATE INDEX IF NOT EXISTS ix_workflow_annotations_id ON portal.workflow_annotations USING btree (id);

CREATE TABLE IF NOT EXISTS portal.workflow_plugin_association (
    workflow_id character varying,
    plugin_id character varying,
    CONSTRAINT workflow_plugin_association_plugin_id_fkey
        FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id) ON DELETE CASCADE,
    CONSTRAINT workflow_plugin_association_workflow_id_fkey
        FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id) ON DELETE CASCADE
);

-- Catch-up for schemas created from 2026-09-28 on ---------------------------------------------------

-- workflows.workflow_type (2026-10-02) comes first: the is_sds backfill below reads it.
ALTER TABLE portal.workflows ADD COLUMN IF NOT EXISTS workflow_type character varying;

-- workflows.is_sds is backfilled only when it is created: until 2026-10-02 a set workflow_type marked an
-- SDS package, but since then every workflow has a type, so a second backfill would mark root-.cwl
-- workflows as SDS.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'portal' AND table_name = 'workflows' AND column_name = 'is_sds') THEN
        ALTER TABLE portal.workflows ADD COLUMN is_sds boolean;
        UPDATE portal.workflows SET is_sds = (workflow_type IS NOT NULL);
    END IF;
END $$;

ALTER TABLE portal.workflows
    ADD COLUMN IF NOT EXISTS seek_project_id integer,
    ADD COLUMN IF NOT EXISTS has_backend boolean,
    ADD COLUMN IF NOT EXISTS frontend_folder character varying,
    ADD COLUMN IF NOT EXISTS frontend_build_command character varying,
    ADD COLUMN IF NOT EXISTS backend_folder character varying;

ALTER TABLE portal.plugins ADD COLUMN IF NOT EXISTS seek_project_id integer;

ALTER TABLE portal.plugin_builds
    ADD COLUMN IF NOT EXISTS handoff_status character varying,
    ADD COLUMN IF NOT EXISTS upload_id character varying,
    ADD COLUMN IF NOT EXISTS dataset_uuid character varying,
    ADD COLUMN IF NOT EXISTS seek_id character varying,
    ADD COLUMN IF NOT EXISTS handoff_error text,
    ADD COLUMN IF NOT EXISTS handoff_user character varying;

ALTER TABLE portal.workflow_builds
    ADD COLUMN IF NOT EXISTS handoff_status character varying,
    ADD COLUMN IF NOT EXISTS upload_id character varying,
    ADD COLUMN IF NOT EXISTS dataset_uuid character varying,
    ADD COLUMN IF NOT EXISTS seek_id character varying,
    ADD COLUMN IF NOT EXISTS handoff_error text,
    ADD COLUMN IF NOT EXISTS handoff_user character varying,
    ADD COLUMN IF NOT EXISTS tool_name character varying,
    ADD COLUMN IF NOT EXISTS bundle_path character varying,
    ADD COLUMN IF NOT EXISTS tool_dataset_uuid character varying;

-- A deployment runs the backend of either a tool build or a gui workflow's build (2026-10-02).
ALTER TABLE portal.plugin_deployments
    ADD COLUMN IF NOT EXISTS workflow_build_id character varying,
    ALTER COLUMN plugin_id DROP NOT NULL,
    ALTER COLUMN build_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE connamespace = 'portal'::regnamespace
                   AND conname = 'plugin_deployments_workflow_build_id_fkey') THEN
        ALTER TABLE portal.plugin_deployments ADD CONSTRAINT plugin_deployments_workflow_build_id_fkey
            FOREIGN KEY (workflow_build_id) REFERENCES portal.workflow_builds(build_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE connamespace = 'portal'::regnamespace
                   AND conname = 'ck_plugin_deployments_one_build') THEN
        ALTER TABLE portal.plugin_deployments ADD CONSTRAINT ck_plugin_deployments_one_build
            CHECK (((build_id IS NULL) <> (workflow_build_id IS NULL)));
    END IF;
END $$;
