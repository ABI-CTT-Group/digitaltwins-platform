# A registered model is described in FHIR as a Device (current decision)

- **Date:** 2026-10-12
- **Status:** Accepted — current decision, expected to be revisited

## Context

Model registration can optionally publish the model to HAPI FHIR. Neither
fhir-cda nor digitaltwins-on-fhir has a model resource, so the resource is built
in this repo. Tool ActivityDefinitions already cite models by dataset UUID as
`participant` entries of type `device` (digitaltwins-on-fhir `workflow_tool.py`).

## Alternatives Considered

### Option A: Device (chosen)
- Pros: R4 Device covers software, including AI/ML models; lines up with tool
  ActivityDefinitions, which list models as `device` participants; identified
  by the dataset UUID under the same identifier system.
- Cons: Device is broad; a richer model card would need extensions.

### Option B: DocumentReference
- Pros: simple; attachments can point at the files.
- Cons: loses the "this is a model" meaning.

### Option C: Library
- Pros: holds knowledge artifacts with content attachments.
- Cons: unusual for ML models; nothing else in the platform uses it.

## Decision

One Device per model dataset, built by `digitaltwins.models.fhir` and pushed
with the plain FHIR REST client (`HapiRest`), delete-then-create keyed on the
identifier:

- `identifier` = dataset UUID, system `https://www.auckland.ac.nz/en/abi.html`
  (digitaltwins-on-fhir's `DIGITALTWIN_ON_FHIR_SYSTEM`)
- `deviceName` = dataset name (`user-friendly-name`), `type.text` = `model`
- client-set `version` (Device.version) and `description` (Device.note)

FHIR is optional: off by default in the portal, `fhir=none` by default in the API.

## Consequences

- The Device JSON is stored as `models/<uuid>/fhir.json`, like other categories.
- If a model representation is later settled upstream (e.g. in
  digitaltwins-on-fhir), this module is replaced and this ADR superseded; the
  annotation shape `{"model": {...}}` can stay.
