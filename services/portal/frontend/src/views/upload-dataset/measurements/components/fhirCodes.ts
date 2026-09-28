/**
 * Static FHIR code lists used by the measurements annotation step.
 *
 * Kept tiny on purpose — the goal is "common clinical defaults the user
 * recognises", not a comprehensive terminology browser. Anyone who needs a
 * code outside these lists can type a free-form value into the underlying
 * v-combobox; the list only drives the dropdown suggestions.
 */

/** A small subset of LOINC codes that cover the most-common Observations. */
export const LOINC_CODES: Array<{ code: string; display: string }> = [
  { code: '8302-2', display: 'Body height' },
  { code: '29463-7', display: 'Body weight' },
  { code: '39156-5', display: 'Body mass index (BMI)' },
  { code: '8867-4', display: 'Heart rate' },
  { code: '8480-6', display: 'Systolic blood pressure' },
  { code: '8462-4', display: 'Diastolic blood pressure' },
  { code: '8310-5', display: 'Body temperature' },
  { code: '2708-6', display: 'Oxygen saturation' },
  { code: '30525-0', display: 'Age' },
];

/** Coding systems the UI suggests for Observation.code.codeSystem. */
export const FHIR_OBSERVATION_SYSTEMS: string[] = [
  'http://loinc.org',
  'http://snomed.info/sct',
  'http://dicom.nema.org/resources/ontology/DCM',
  'https://12labours.org/measurement-system',
];

/**
 * Curated SNOMED CT body-site codes for ImagingStudy series. Stored as
 * fully-shaped Coding objects so the binder can drop them straight into
 * fhir-cda's series.bodySite slot (system + code + display required).
 */
export const SNOMED_BODY_SITES: Array<{
  system: string;
  code: string;
  display: string;
}> = [
  { system: 'http://snomed.info/sct', code: '76752008', display: 'Breast structure' },
  { system: 'http://snomed.info/sct', code: '80891009', display: 'Heart structure' },
  { system: 'http://snomed.info/sct', code: '39607008', display: 'Lung structure' },
  { system: 'http://snomed.info/sct', code: '10200004', display: 'Liver structure' },
  { system: 'http://snomed.info/sct', code: '64033007', display: 'Kidney structure' },
  { system: 'http://snomed.info/sct', code: '12738006', display: 'Brain structure' },
  { system: 'http://snomed.info/sct', code: '69536005', display: 'Head structure' },
  { system: 'http://snomed.info/sct', code: '38266002', display: 'Entire body' },
];

/** Common MIME types for DocumentReference attachments. */
export const COMMON_CONTENT_TYPES: string[] = [
  'model/obj',
  'application/pdf',
  'text/csv',
  'application/json',
  'image/png',
  'image/jpeg',
  'application/vnd.ms-excel',
  'application/octet-stream',
];
