/**
 * Measurement API client (plan 07).
 *
 * Mirrors the workflow client shape (one function per endpoint), but:
 *  - No `latestBuild` enrichment — measurements have no builds table.
 *    `useMeasurement()` is a plain list fetch; status lives on the row.
 *  - `_auto` markers in the descriptions tree are UI-only and stripped
 *    client-side before being POSTed to `/annotation`.
 *  - upsertAnnotation behaviour: server is expected to update if the
 *    annotation row already exists for this measurement (retry-friendly).
 */

import http from "./http";
import type {
  MeasurementInformationStep,
  MeasurementResponse,
  MeasurementTreeResponse,
  MeasurementAnnotationResponse,
  MeasurementDeleteResponse,
  FhirCdaDescriptions,
} from "@/models/types";

/** GET /api/measurement — list all measurements. */
export async function useMeasurement(): Promise<MeasurementResponse[]> {
  return http.get<MeasurementResponse[]>(`/measurement/`);
}

/** GET /api/measurement/{id} — fetch a single measurement row (status polling). */
export async function useGetMeasurement(id: string): Promise<MeasurementResponse> {
  return http.get<MeasurementResponse>(`/measurement/${id}`);
}

/** POST /api/measurement/create — create after upload-source. */
export async function useCreateMeasurement(
  payload: MeasurementInformationStep,
): Promise<MeasurementResponse> {
  return http.post<MeasurementResponse>(`/measurement/create`, payload);
}

/** GET /api/measurement/{id}/tree — server-classified prefilled descriptions. */
export async function useGetMeasurementTree(id: string): Promise<MeasurementTreeResponse> {
  return http.get<MeasurementTreeResponse>(`/measurement/${id}/tree`);
}

/** GET /api/measurement/{id}/annotation — fetch existing annotation (rehydrate). */
export async function useGetMeasurementAnnotation(
  id: string,
): Promise<MeasurementAnnotationResponse> {
  return http.get<MeasurementAnnotationResponse>(`/measurement/${id}/annotation`);
}

/**
 * POST /api/measurement/{id}/annotation — create-or-update the descriptions.
 *
 * IMPORTANT: caller must strip `_auto` fields recursively before invoking
 * (see `stripAuto` in `views/upload-dataset/measurements/components/`).
 */
export async function useUpsertMeasurementAnnotation(
  id: string,
  descriptions: FhirCdaDescriptions,
): Promise<MeasurementAnnotationResponse> {
  return http.post<MeasurementAnnotationResponse>(
    `/measurement/${id}/annotation`,
    { descriptions },
  );
}

/** POST /api/measurement/{id}/submit — synchronously kicks off the 6-stage pipeline. */
export async function useMeasurementSubmit(id: string): Promise<MeasurementResponse> {
  return http.post<MeasurementResponse>(`/measurement/${id}/submit`, {});
}

/** POST /api/measurement/{id}/retry-fhir — idempotent retry of stages 4-6. */
export async function useMeasurementRetryFhir(id: string): Promise<MeasurementResponse> {
  return http.post<MeasurementResponse>(`/measurement/${id}/retry-fhir`, {});
}

/** DELETE /api/measurement/{id}. */
export async function useDeleteMeasurement(id: string): Promise<MeasurementDeleteResponse> {
  return http.delete<MeasurementDeleteResponse>(`/measurement/${id}`);
}
