/**
 * Measurement API client.
 *
 * Mirrors the workflow client shape (one function per endpoint), but:
 *  - No `latestBuild` enrichment — measurements have no builds table.
 *    `useMeasurement()` is a plain list fetch; status lives on the row.
 *  - `_auto` markers in the descriptions tree are UI hints. They are persisted
 *    with the draft (so reopening a saved annotation keeps the auto-classified
 *    count + chips) and are inert downstream — `apply_descriptions` builds
 *    fhir.json from named fields only and never serialises `_auto`.
 *  - upsertAnnotation behaviour: server is expected to update if the
 *    annotation row already exists for this measurement (retry-friendly).
 */

import http from "./http";
import type {
  MeasurementResponse,
  MeasurementTreeResponse,
  MeasurementAnnotationResponse,
  MeasurementDeleteResponse,
  FhirCdaDescriptions,
} from "@/models/types";

/**
 * Runtime config surfaced by the backend so the Information step's dropzone
 * picks up the operator-configured upload ceiling without a frontend
 * rebuild. Driven by MAX_UPLOAD_MB in .env.
 */
export interface MeasurementConfig {
  maxUploadBytes: number;
  maxUploadMb: number;
}

export async function useMeasurementConfig(): Promise<MeasurementConfig> {
  return http.get<MeasurementConfig>(`/measurement/config`);
}

/** GET /api/measurement — list all measurements. */
export async function useMeasurement(): Promise<MeasurementResponse[]> {
  return http.get<MeasurementResponse[]>(`/measurement/`);
}

/** GET /api/measurement/{id} — fetch a single measurement row (status polling). */
export async function useGetMeasurement(id: string): Promise<MeasurementResponse> {
  return http.get<MeasurementResponse>(`/measurement/${id}`);
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
 * The `_auto` UI markers are persisted as-is (they round-trip through the
 * lenient `descriptions: dict` schema) so a reopened draft keeps its
 * auto-classified count + chips. They are ignored when fhir.json is built.
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

/**
 * GET /api/measurement/{id}/fhir-preview — dry-run build of the real fhir.json
 * (no upload). Backs the Preview page and the Export action. Endpoint URLs are
 * placeholders until the dataset is approved/uploaded (finalize rewrites them).
 */
export async function useMeasurementFhirPreview(id: string): Promise<Record<string, any>> {
  return http.get<Record<string, any>>(`/measurement/${id}/fhir-preview`);
}

/** DELETE /api/measurement/{id}. */
export async function useDeleteMeasurement(id: string): Promise<MeasurementDeleteResponse> {
  return http.delete<MeasurementDeleteResponse>(`/measurement/${id}`);
}

// ---------------------------------------------------------------------------
// Chunked upload (Approach A) — control-plane endpoints.
//
// The part PUTs are NOT here: they send raw octet-stream bytes and live in
// `measurement_upload.ts`, which calls the interceptor-bearing axios instance
// directly so a mid-upload 401 still triggers the keycloak refresh+retry.
// init / status / finalize / cancel are ordinary JSON and use the http wrapper.
// ---------------------------------------------------------------------------

export interface UploadManifestEntry {
  relPath: string;
  size: number;
  parts: number;
}

export interface UploadInitPayload {
  name: string;
  description?: string;
  sourceKind: 'folder' | 'zip';
  manifest: UploadManifestEntry[];
}

export interface UploadInitResponse {
  measurementId: string;
  maxPartSize: number;
}

export interface UploadStatusFile {
  relPath: string;
  size: number;
  parts: number;
  receivedParts: number[];
  bytes: number;
  complete: boolean;
}

export interface UploadStatusResponse {
  sourceKind: 'folder' | 'zip';
  files: UploadStatusFile[];
  complete: boolean;
}

/** POST /api/measurement/upload/init — pre-create row + chunk store. */
export async function useUploadInit(payload: UploadInitPayload): Promise<UploadInitResponse> {
  return http.post<UploadInitResponse>(`/measurement/upload/init`, payload);
}

/** GET /api/measurement/upload/{id}/status — received parts, for resume. */
export async function useUploadStatus(id: string): Promise<UploadStatusResponse> {
  return http.get<UploadStatusResponse>(`/measurement/upload/${id}/status`);
}

/** POST /api/measurement/upload/{id}/finalize — assemble + validate + move. */
export async function useUploadFinalize(id: string): Promise<MeasurementResponse> {
  return http.post<MeasurementResponse>(`/measurement/upload/${id}/finalize`, {});
}

/** POST /api/measurement/upload/{id}/cancel — drop tmp parts + delete row. */
export async function useUploadCancel(id: string): Promise<{ success: boolean; id: string }> {
  return http.post<{ success: boolean; id: string }>(`/measurement/upload/${id}/cancel`, {});
}
