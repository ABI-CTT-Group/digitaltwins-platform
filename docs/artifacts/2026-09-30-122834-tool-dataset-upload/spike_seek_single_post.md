# Spike: register a tool in SEEK with one RO-Crate POST (2026-09-30)

Target: local SEEK (`ldh:v0.3.2`, `git_support_enabled = true`). Auth: the platform admin's Keycloak JWT from a password grant, client `api`, sent as `Authorization: Bearer <REDACTED>`.

Request: `POST /seek/workflows`, multipart:
- `ro_crate`: a zip of a hand-built `ro-crate-metadata.json` + `tool_dicom_to_nifti.cwl`
  - root `name`: the CWL label
  - root `keywords`: `["tool","script"]`
  - `mainEntity`: the CWL file
  - `programmingLanguage`: `#cwl`
- `workflow[project_ids][]=10`

## Results
| Check | Result |
|---|---|
| Status | 200 on a single call (no PATCH, no delete) |
| Title | `Tool - dicom to nifti` (CWL `label`, no "Research Object Crate for" prefix) |
| Tags | `script`, `tool` |
| workflow_class | `cwl` |
| internals.inputs | `#main/dicom_input`, description `measurements`, type Directory |
| internals.outputs | `#main/rai_nifti_output`, description `measurements`, type File |
| Listed by `GET /workflows?filter[tag]=tool` | yes |
| Bearer JWT on multipart | accepted (no CSRF rejection) |
| `DELETE /workflows/{id}` | 200 (test workflow 42 removed) |

## Gotcha
Sending `Accept: application/json` on the multipart POST gives **422** "A POST/PUT request must have a data record complying with JSONAPI specs" (`application_controller.rb:501`). SEEK then treats the request as a JSON:API call and requires a `data` body. The writer must send only `Authorization` on this POST; the response is JSON anyway. JSON calls such as DELETE and GET keep `Accept: application/json`.

The example CWL has no top-level `doc`, so the description is empty.
