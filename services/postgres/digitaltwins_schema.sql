--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: assay; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assay (
    assay_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    assay_seek_id integer,
    workflow_seek_id integer,
    cohort integer,
    ready boolean
);


--
-- Name: assay_input; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assay_input (
    assay_uuid uuid,
    name character varying,
    dataset_uuid character varying,
    sample_type character varying,
    category character varying
);


--
-- Name: assay_output; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assay_output (
    assay_uuid uuid,
    name character varying,
    dataset_name character varying,
    sample_name character varying,
    category character varying
);


--
-- Name: code_description; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.code_description (
    dataset_uuid uuid,
    code_uuid uuid NOT NULL
);


--
-- Name: code_parameter; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.code_parameter (
    dataset_uuid uuid,
    code_uuid uuid NOT NULL
);


--
-- Name: dataset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataset (
    project_uuid uuid NOT NULL,
    dataset_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    dataset_id integer,
    version integer DEFAULT 1,
    category character varying NOT NULL,
    dataset_name character varying,
    seek_id character varying
);


--
-- Name: dataset_description; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataset_description (
    dataset_uuid uuid NOT NULL,
    metadata_version character varying DEFAULT '2.0.0'::character varying NOT NULL,
    dataset_type character varying,
    title character varying,
    subtitle character varying,
    keywords character varying[],
    funding character varying[],
    acknowledgments character varying,
    study_purpose character varying,
    study_data_collection character varying,
    study_primary_conclusion character varying,
    study_organ_system character varying[],
    study_approach character varying[],
    study_technique character varying[],
    study_collection_title character varying,
    contributor_name character varying[],
    contributor_orcid character varying[],
    contributor_affiliation character varying[],
    contributor_role character varying[],
    identifier_description character varying[],
    relation_type character varying[],
    identifier character varying[],
    identifier_type character varying[],
    number_of_subjects integer,
    number_of_samples integer
);


--
-- Name: dataset_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dataset_mapping (
    dataset_uuid uuid NOT NULL,
    subject_uuid uuid NOT NULL,
    sample_uuid uuid NOT NULL,
    subject_id character varying(100),
    sample_id character varying(100)
);


--
-- Name: manifest; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manifest (
    dataset_uuid uuid NOT NULL,
    filename character varying,
    "timestamp" character varying,
    description character varying,
    file_type character varying,
    additional_metadata character varying,
    additional_types character varying
);


--
-- Name: performance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.performance (
    dataset_uuid uuid,
    performance_uuid uuid NOT NULL
);


--
-- Name: program; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.program (
    program_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    program_name character varying,
    seek_id character varying
);


--
-- Name: project; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project (
    program_uuid uuid NOT NULL,
    project_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    project_name character varying,
    seek_id character varying
);


--
-- Name: resource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource (
    dataset_uuid uuid,
    resource_uuid uuid NOT NULL
);


--
-- Name: sample; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sample (
    sample_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    was_derived_from_sample character varying,
    pool_id character varying,
    sample_experimental_group character varying,
    sample_type character varying,
    sample_anatomical_location character varying,
    also_in_dataset character varying,
    member_of character varying,
    laboratory_internal_id character varying,
    date_of_derivation character varying,
    experimental_log_file_path character varying,
    reference_atlas character varying,
    pathology character varying,
    laterality character varying,
    cell_type character varying,
    plane_of_section character varying,
    protocol_title character varying,
    protocol_url_or_doi character varying
);


--
-- Name: subject; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subject (
    subject_uuid uuid DEFAULT public.uuid_generate_v1() NOT NULL,
    pool_id character varying,
    subject_experimental_group character varying,
    age character varying,
    sex character varying,
    species character varying,
    strain character varying,
    rrid_for_strain character varying,
    age_category character varying,
    also_in_dataset character varying,
    member_of character varying,
    laboratory_internal_id character varying,
    date_of_birth character varying,
    age_range_min character varying,
    age_range_max character varying,
    body_mass character varying,
    genotype character varying,
    phenotype character varying,
    handedness character varying,
    reference_atlas character varying,
    experimental_log_file_path character varying,
    experiment_date character varying,
    disease_or_disorder character varying,
    intervention character varying,
    disease_model character varying,
    protocol_title character varying,
    protocol_url_or_doi character varying
);


--
-- Name: submission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission (
    dataset_uuid uuid,
    submission uuid NOT NULL
);


--
-- Name: workflow; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workflow (
    dataset_uuid uuid,
    field_type character varying,
    field_name character varying,
    field_label character varying
);


--
-- Name: code_description code_description_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_description
    ADD CONSTRAINT code_description_pkey PRIMARY KEY (code_uuid);


--
-- Name: code_parameter code_parameter_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_parameter
    ADD CONSTRAINT code_parameter_pkey PRIMARY KEY (code_uuid);


--
-- Name: dataset_description dataset_description_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_description
    ADD CONSTRAINT dataset_description_pkey PRIMARY KEY (dataset_uuid);


--
-- Name: dataset_mapping dataset_mapping_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_mapping
    ADD CONSTRAINT dataset_mapping_pk PRIMARY KEY (dataset_uuid, subject_uuid, sample_uuid);


--
-- Name: dataset dataset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset
    ADD CONSTRAINT dataset_pkey PRIMARY KEY (dataset_uuid);


--
-- Name: performance performance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance
    ADD CONSTRAINT performance_pkey PRIMARY KEY (performance_uuid);


--
-- Name: program program_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program
    ADD CONSTRAINT program_pkey PRIMARY KEY (program_uuid);


--
-- Name: project project_uuid; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_uuid PRIMARY KEY (project_uuid);


--
-- Name: resource resource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource
    ADD CONSTRAINT resource_pkey PRIMARY KEY (resource_uuid);


--
-- Name: sample sample_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sample
    ADD CONSTRAINT sample_pkey PRIMARY KEY (sample_uuid);


--
-- Name: subject subject_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject
    ADD CONSTRAINT subject_pkey PRIMARY KEY (subject_uuid);


--
-- Name: submission submission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_pkey PRIMARY KEY (submission);


--
-- Name: manifest dataset; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manifest
    ADD CONSTRAINT dataset FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid);


--
-- Name: dataset_description dataset; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_description
    ADD CONSTRAINT dataset FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid);


--
-- Name: dataset_mapping dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_mapping
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid);


--
-- Name: code_description dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_description
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid) NOT VALID;


--
-- Name: code_parameter dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_parameter
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid) NOT VALID;


--
-- Name: performance dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid) NOT VALID;


--
-- Name: resource dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid) NOT VALID;


--
-- Name: submission dataset_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT dataset_uuid FOREIGN KEY (dataset_uuid) REFERENCES public.dataset(dataset_uuid) NOT VALID;


--
-- Name: project program; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT program FOREIGN KEY (program_uuid) REFERENCES public.program(program_uuid) NOT VALID;


--
-- Name: dataset project; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset
    ADD CONSTRAINT project FOREIGN KEY (project_uuid) REFERENCES public.project(project_uuid) NOT VALID;


--
-- Name: dataset_mapping sample_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_mapping
    ADD CONSTRAINT sample_uuid FOREIGN KEY (sample_uuid) REFERENCES public.sample(sample_uuid);


--
-- Name: dataset_mapping subject_uuid; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dataset_mapping
    ADD CONSTRAINT subject_uuid FOREIGN KEY (subject_uuid) REFERENCES public.subject(subject_uuid);


--
-- PostgreSQL database dump complete
--

