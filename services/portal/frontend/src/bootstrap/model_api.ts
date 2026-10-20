/**
 * Model API client — model datasets in the platform API.
 *
 * Models upload through the same chunked sessions as measurements
 * (`ChunkedUploader` with `category: 'models'`) and share their lifecycle, so
 * a model is a `MeasurementResponse`: an upload session (`upload:<id>`) until
 * approved, then a committed dataset (`dataset:<uuid>`). Approve, cancel,
 * delete, FHIR push and preview reuse the generic helpers in measurement_api.
 * The optional FHIR annotation is `{"model": {description, version}}`, pushed
 * as one Device.
 */

import { dtApi } from "./http";
import {
  datasetToMeasurement,
  sessionToMeasurement,
  splitMeasurementId,
  type PlatformDataset,
  type UploadSession,
} from "./measurement_api";
import type { MeasurementResponse } from "@/models/types";

export const MODEL_CATEGORY = "models";

/** Client-set fields of a model's FHIR Device. */
export interface ModelFhirFields {
  description: string;
  version: string;
}

function fhirBase(id: string): string {
  const { kind, rawId } = splitMeasurementId(id);
  return kind === "dataset" ? `/datasets/${rawId}/fhir` : `/datasets/uploads/${rawId}/fhir`;
}

/** Every model: uploads not yet committed + registered model datasets, newest first. */
export async function useModels(): Promise<MeasurementResponse[]> {
  const [uploads, models] = await Promise.all([
    dtApi.get<{ uploads: UploadSession[] }>(`/datasets/uploads`, { category: MODEL_CATEGORY }),
    dtApi.get<{ models: PlatformDataset[] }>(`/models`),
  ]);
  return [
    ...uploads.uploads.map(sessionToMeasurement),
    ...models.models.map(datasetToMeasurement),
  ].sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
}

/** The model's current FHIR fields: the stored annotation, or the server's defaults. */
export async function useModelFhirDraft(id: string): Promise<ModelFhirFields> {
  const res = await dtApi.get<{ descriptions: { model: ModelFhirFields } }>(`${fhirBase(id)}/tree`);
  const { description = "", version = "" } = res.descriptions.model;
  return { description, version };
}

/** Store the FHIR annotation (a staged upload's draft, or a registered model's). */
export async function useUpsertModelAnnotation(id: string, fields: ModelFhirFields): Promise<void> {
  await dtApi.put(`${fhirBase(id)}/annotation`, { descriptions: { model: fields } });
}
