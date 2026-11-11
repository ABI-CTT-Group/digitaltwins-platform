-- prune-digitaltwins.sql — run on the TARGET after util/portal-restore.sh.
-- Keeps only the demo scope: assays 41/42/43 and the 10 datasets they use.
-- The restored portal schema already holds only the three needed workflows
-- (image_conversion/89, mri_curation/97, volview/95) — no pruning needed there.
--
-- Run:  docker exec -i digitaltwins-platform-database-1 \
--         psql -U admin -d digitaltwins -v ON_ERROR_STOP=1 < prune-digitaltwins.sql
BEGIN;

CREATE TEMP TABLE keep_datasets(uuid uuid PRIMARY KEY) ON COMMIT DROP;
INSERT INTO keep_datasets VALUES
  -- measurements
  ('e77702f0-c054-11f1-9c10-0abece750f00'), -- test_dicom
  ('754c4202-c055-11f1-9010-0abece750f00'), -- test_curated_dataset
  ('8dfbb026-c05f-11f1-96af-0abece750f00'), -- test_converted
  -- tools
  ('74e61c96-c034-11f1-b090-0abece750f00'), -- tool_dicom_to_nifti (seek 87)
  ('750ca604-c034-11f1-9125-0abece750f00'), -- tool_dicom_to_nrrd (seek 88)
  ('1a5830fa-c054-11f1-9b12-0abece750f00'), -- tool_mri_curation (seek 96)
  ('718cb9b2-c041-11f1-a748-0abece750f00'), -- tool_volview (seek 94)
  -- workflows
  ('752540e2-c034-11f1-ae39-0abece750f00'), -- workflow_image_conversion (seek 89)
  ('1a6c77d6-c054-11f1-95f9-0abece750f00'), -- workflow_mri_curation (seek 97)
  ('7434f526-c041-11f1-a51b-0abece750f00'); -- workflow_volview (seek 95)

-- assays: keep 41/42/43 (assay_input/assay_output have no FK -> delete first)
DELETE FROM assay_input  WHERE assay_uuid IN (SELECT assay_uuid FROM assay WHERE assay_seek_id NOT IN (41,42,43));
DELETE FROM assay_output WHERE assay_uuid IN (SELECT assay_uuid FROM assay WHERE assay_seek_id NOT IN (41,42,43));
DELETE FROM assay WHERE assay_seek_id NOT IN (41,42,43);

-- dataset children first (NO ACTION FKs), then datasets
DELETE FROM code_description     WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM code_parameter       WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM dataset_description  WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM dataset_mapping      WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM manifest             WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM performance          WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM resource             WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM submission           WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM upload_session       WHERE dataset_uuid IS NOT NULL
                                   AND dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);
DELETE FROM workflow_tool        WHERE workflow_dataset_uuid NOT IN (SELECT uuid FROM keep_datasets)
                                    OR tool_dataset_uuid     NOT IN (SELECT uuid FROM keep_datasets);
-- dataset_fhir_annotation cascades from dataset
DELETE FROM dataset WHERE dataset_uuid NOT IN (SELECT uuid FROM keep_datasets);

-- subjects/samples no longer referenced by any mapping
DELETE FROM sample  s WHERE NOT EXISTS (SELECT 1 FROM dataset_mapping m WHERE m.sample_uuid  = s.sample_uuid);
DELETE FROM subject s WHERE NOT EXISTS (SELECT 1 FROM dataset_mapping m WHERE m.subject_uuid = s.subject_uuid);

-- report: must show 10 datasets, 3 assays (41,42,43)
SELECT 'dataset' AS tbl, count(*) FROM dataset
UNION ALL SELECT 'assay', count(*) FROM assay
UNION ALL SELECT 'assay_input', count(*) FROM assay_input
UNION ALL SELECT 'assay_output', count(*) FROM assay_output
UNION ALL SELECT 'dataset_mapping', count(*) FROM dataset_mapping
UNION ALL SELECT 'subject', count(*) FROM subject
UNION ALL SELECT 'sample', count(*) FROM sample;
SELECT assay_seek_id, workflow_seek_id, cohort, ready FROM assay ORDER BY assay_seek_id;
SELECT dataset_name, category, seek_id FROM dataset ORDER BY category, dataset_name;

COMMIT;
