-- The portal schema as the builder created it at commit bf7a3325 (2026-09-28), when the portal
-- tables moved to Postgres: the oldest schema the builder's migrations must catch up.
-- pg_dump --schema-only --schema=portal --no-owner --no-privileges, without psql meta-commands and SET lines.

CREATE SCHEMA portal;

CREATE TYPE portal.plugin_label AS ENUM (
    'GUI',
    'Script'
);

CREATE TABLE portal.measurement_annotations (
    id character varying NOT NULL,
    measurement_id character varying NOT NULL,
    annotation_id character varying NOT NULL,
    descriptions json,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.measurements (
    id character varying NOT NULL,
    uuid character varying,
    name character varying NOT NULL,
    description text,
    dataset_path character varying,
    expose_name character varying,
    s3_path character varying,
    local_archive_path character varying,
    status character varying NOT NULL,
    failure_stage character varying,
    failure_message text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.plugin_annotations (
    id character varying NOT NULL,
    plugin_id character varying NOT NULL,
    annotation_id character varying NOT NULL,
    sparc_note character varying,
    fhir_note character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.plugin_builds (
    id character varying NOT NULL,
    plugin_id character varying NOT NULL,
    build_id character varying NOT NULL,
    status character varying NOT NULL,
    build_logs text,
    error_messages text,
    s3_path character varying,
    expose_name character varying,
    dataset_path character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.plugin_deployments (
    id character varying NOT NULL,
    plugin_id character varying NOT NULL,
    build_id character varying NOT NULL,
    deploy_id character varying NOT NULL,
    status character varying NOT NULL,
    source_path character varying,
    up boolean,
    route_prefix character varying,
    internal_host character varying,
    internal_port character varying,
    has_websocket boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.plugins (
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
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.workflow_annotations (
    id character varying NOT NULL,
    workflow_id character varying NOT NULL,
    annotation_id character varying NOT NULL,
    fhir_note character varying,
    sparc_note character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.workflow_builds (
    id character varying NOT NULL,
    workflow_id character varying NOT NULL,
    build_id character varying NOT NULL,
    status character varying NOT NULL,
    build_logs text,
    error_messages text,
    s3_path character varying,
    expose_name character varying,
    dataset_path character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE portal.workflow_plugin_association (
    workflow_id character varying,
    plugin_id character varying
);

CREATE TABLE portal.workflows (
    id character varying NOT NULL,
    uuid character varying,
    name character varying NOT NULL,
    version character varying NOT NULL,
    description text,
    author character varying,
    repository_url character varying NOT NULL,
    source_type character varying NOT NULL,
    local_archive_path character varying,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

ALTER TABLE ONLY portal.measurement_annotations
    ADD CONSTRAINT measurement_annotations_measurement_id_key UNIQUE (measurement_id);

ALTER TABLE ONLY portal.measurement_annotations
    ADD CONSTRAINT measurement_annotations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.measurements
    ADD CONSTRAINT measurements_expose_name_key UNIQUE (expose_name);

ALTER TABLE ONLY portal.measurements
    ADD CONSTRAINT measurements_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.measurements
    ADD CONSTRAINT measurements_uuid_key UNIQUE (uuid);

ALTER TABLE ONLY portal.plugin_annotations
    ADD CONSTRAINT plugin_annotations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.plugin_builds
    ADD CONSTRAINT plugin_builds_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.plugin_deployments
    ADD CONSTRAINT plugin_deployments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.plugins
    ADD CONSTRAINT plugins_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.plugins
    ADD CONSTRAINT plugins_uuid_key UNIQUE (uuid);

ALTER TABLE ONLY portal.workflow_annotations
    ADD CONSTRAINT workflow_annotations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.workflow_builds
    ADD CONSTRAINT workflow_builds_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (id);

ALTER TABLE ONLY portal.workflows
    ADD CONSTRAINT workflows_uuid_key UNIQUE (uuid);

CREATE UNIQUE INDEX ix_measurement_annotations_annotation_id ON portal.measurement_annotations USING btree (annotation_id);

CREATE INDEX ix_measurement_annotations_id ON portal.measurement_annotations USING btree (id);

CREATE INDEX ix_measurements_id ON portal.measurements USING btree (id);

CREATE INDEX ix_measurements_name ON portal.measurements USING btree (name);

CREATE UNIQUE INDEX ix_plugin_annotations_annotation_id ON portal.plugin_annotations USING btree (annotation_id);

CREATE INDEX ix_plugin_annotations_id ON portal.plugin_annotations USING btree (id);

CREATE UNIQUE INDEX ix_plugin_builds_build_id ON portal.plugin_builds USING btree (build_id);

CREATE INDEX ix_plugin_builds_id ON portal.plugin_builds USING btree (id);

CREATE UNIQUE INDEX ix_plugin_deployments_deploy_id ON portal.plugin_deployments USING btree (deploy_id);

CREATE INDEX ix_plugin_deployments_id ON portal.plugin_deployments USING btree (id);

CREATE INDEX ix_plugins_id ON portal.plugins USING btree (id);

CREATE INDEX ix_plugins_name ON portal.plugins USING btree (name);

CREATE UNIQUE INDEX ix_workflow_annotations_annotation_id ON portal.workflow_annotations USING btree (annotation_id);

CREATE INDEX ix_workflow_annotations_id ON portal.workflow_annotations USING btree (id);

CREATE UNIQUE INDEX ix_workflow_builds_build_id ON portal.workflow_builds USING btree (build_id);

CREATE INDEX ix_workflow_builds_id ON portal.workflow_builds USING btree (id);

CREATE INDEX ix_workflows_id ON portal.workflows USING btree (id);

CREATE INDEX ix_workflows_name ON portal.workflows USING btree (name);

ALTER TABLE ONLY portal.measurement_annotations
    ADD CONSTRAINT measurement_annotations_measurement_id_fkey FOREIGN KEY (measurement_id) REFERENCES portal.measurements(id) ON DELETE CASCADE;

ALTER TABLE ONLY portal.plugin_annotations
    ADD CONSTRAINT plugin_annotations_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id);

ALTER TABLE ONLY portal.plugin_builds
    ADD CONSTRAINT plugin_builds_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id);

ALTER TABLE ONLY portal.plugin_deployments
    ADD CONSTRAINT plugin_deployments_build_id_fkey FOREIGN KEY (build_id) REFERENCES portal.plugin_builds(build_id);

ALTER TABLE ONLY portal.plugin_deployments
    ADD CONSTRAINT plugin_deployments_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id);

ALTER TABLE ONLY portal.workflow_annotations
    ADD CONSTRAINT workflow_annotations_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id);

ALTER TABLE ONLY portal.workflow_builds
    ADD CONSTRAINT workflow_builds_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id);

ALTER TABLE ONLY portal.workflow_plugin_association
    ADD CONSTRAINT workflow_plugin_association_plugin_id_fkey FOREIGN KEY (plugin_id) REFERENCES portal.plugins(id) ON DELETE CASCADE;

ALTER TABLE ONLY portal.workflow_plugin_association
    ADD CONSTRAINT workflow_plugin_association_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES portal.workflows(id) ON DELETE CASCADE;

