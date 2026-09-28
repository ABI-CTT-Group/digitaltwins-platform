/**
 * Measurement API client — backed by the platform REST API (digitaltwins-api).
 *
 * Measurement ingest lives in digitaltwins-api (`/digitaltwins-api/datasets/...`).
 * This module adapts it to the `MeasurementResponse` shape the views already use,
 * so a measurement is one of:
 *
 *  - an upload session (`upload:<upload_id>`): receiving parts, staged for
 *    annotation, being committed, or failed to commit. Nothing is in MinIO /
 *    platform Postgres yet; `/approve` commits it (the "Approval" step).
 *  - a committed dataset (`dataset:<dataset_uuid>`): stored in MinIO + Postgres;
 *    its status follows the FHIR push (`fhir_status`).
 *
 * Views treat `id` as opaque; each function routes by its prefix. Polling an
 * `upload:` id after approval follows the session into its dataset.
 *
 * UUIDs in descriptions are assigned by the server when the dataset is
 * committed; the draft of a staged upload carries empty UUIDs.
 */

import { dtApi } from "./http";
import type {
  MeasurementResponse,
  MeasurementTreeResponse,
  MeasurementAnnotationResponse,
  MeasurementDeleteResponse,
  FhirCdaDescriptions,
} from "@/models/types";

// ---------------------------------------------------------------------------
// Server shapes (camelized by the dtApi interceptor) + adapters
// ---------------------------------------------------------------------------

interface UploadSession {
  uploadId: string;
  name: string;
  description?: string;
  status: "receiving" | "staged" | "processing" | "completed" | "failed";
  failureStage?: string;
  failureMessage?: string;
  fhirMode: "none" | "auto" | "descriptions";
  datasetUuid?: string;
  createdAt: string;
  updatedAt: string;
  upload: UploadStatusResponse | null;
}

interface PlatformDataset {
  datasetUuid: string;
  datasetName?: string;
  fhirStatus: "none" | "pending" | "pushing" | "completed" | "failed";
  fhirFailureMessage?: string;
  createdAt?: string;
}

type MeasurementKind = "upload" | "dataset";

/** Split a measurement id into its kind and server id (unprefixed ids are uploads). */
export function splitMeasurementId(id: string): { kind: MeasurementKind; rawId: string } {
  const [prefix, rest] = id.includes(":") ? id.split(/:(.*)/s) : ["upload", id];
  return { kind: prefix === "dataset" ? "dataset" : "upload", rawId: rest };
}

const SESSION_STATUS: Record<string, string> = {
  receiving: "pending_upload",
  staged: "pending",
  processing: "uploading",
  failed: "submit_failed",
};

const FHIR_STATUS: Record<string, string> = {
  none: "completed",
  pending: "uploading",
  pushing: "uploading",
  completed: "completed",
  failed: "fhir_failed",
};

function sessionToMeasurement(s: UploadSession): MeasurementResponse {
  return {
    id: `upload:${s.uploadId}`,
    name: s.name,
    description: s.description,
    status: SESSION_STATUS[s.status] ?? s.status,
    // A failed commit happens while storing the dataset (Postgres + MinIO).
    failureStage: s.status === "failed" ? "upload" : undefined,
    failureMessage: s.failureMessage,
    hasAnnotation: s.fhirMode === "descriptions",
    createdAt: s.createdAt,
    updatedAt: s.updatedAt,
  };
}

function datasetToMeasurement(d: PlatformDataset): MeasurementResponse {
  return {
    id: `dataset:${d.datasetUuid}`,
    uuid: d.datasetUuid,
    name: d.datasetName ?? d.datasetUuid,
    status: FHIR_STATUS[d.fhirStatus] ?? d.fhirStatus,
    failureStage: d.fhirStatus === "failed" ? "fhir_push" : undefined,
    failureMessage: d.fhirFailureMessage,
    // A dataset only reaches FHIR with an annotation.
    hasAnnotation: d.fhirStatus !== "none",
    createdAt: d.createdAt ?? "",
    updatedAt: d.createdAt ?? "",
  };
}

async function getDataset(uuid: string): Promise<PlatformDataset> {
  return (await dtApi.get<{ dataset: PlatformDataset }>(`/datasets/${uuid}`)).dataset;
}

/** Base path of a measurement's FHIR endpoints. */
function fhirBase(id: string): string {
  const { kind, rawId } = splitMeasurementId(id);
  return kind === "dataset" ? `/datasets/${rawId}/fhir` : `/datasets/uploads/${rawId}/fhir`;
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** Upload ceiling for the Information step's dropzone (MAX_UPLOAD_MB on the API). */
export interface MeasurementConfig {
  maxUploadBytes: number;
  maxUploadMb: number;
}

export async function useMeasurementConfig(): Promise<MeasurementConfig> {
  const cfg = await dtApi.get<{ maxUploadBytes: number }>(`/datasets/uploads/config`);
  return { maxUploadBytes: cfg.maxUploadBytes, maxUploadMb: Math.round(cfg.maxUploadBytes / (1024 * 1024)) };
}

/** Every measurement: uploads not yet committed + committed measurement datasets. */
export async function useMeasurement(): Promise<MeasurementResponse[]> {
  const [uploads, datasets] = await Promise.all([
    dtApi.get<{ uploads: UploadSession[] }>(`/datasets/uploads`),
    dtApi.get<{ datasets: PlatformDataset[] }>(`/datasets`, { categories: "measurements" }),
  ]);
  return [
    ...uploads.uploads.map(sessionToMeasurement),
    ...datasets.datasets.map(datasetToMeasurement),
  ].sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
}

/** One measurement (status polling). A committed upload resolves to its dataset. */
export async function useGetMeasurement(id: string): Promise<MeasurementResponse> {
  const { kind, rawId } = splitMeasurementId(id);
  if (kind === "dataset") return datasetToMeasurement(await getDataset(rawId));
  const session = await dtApi.get<UploadSession>(`/datasets/uploads/${rawId}`);
  if (session.status === "completed" && session.datasetUuid) {
    return { ...datasetToMeasurement(await getDataset(session.datasetUuid)), name: session.name };
  }
  return sessionToMeasurement(session);
}

/** Server-classified prefilled descriptions (real UUIDs once committed). */
export async function useGetMeasurementTree(id: string): Promise<MeasurementTreeResponse> {
  return dtApi.get<MeasurementTreeResponse>(`${fhirBase(id)}/tree`);
}

/** Existing annotation (rehydrate); rejects with 404 when there is none. */
export async function useGetMeasurementAnnotation(id: string): Promise<MeasurementAnnotationResponse> {
  const res = await dtApi.get<{ descriptions: FhirCdaDescriptions }>(`${fhirBase(id)}/annotation`);
  return { id, measurementId: id, annotationId: "", descriptions: res.descriptions, createdAt: "", updatedAt: "" };
}

/** Create-or-replace the annotation. `_auto` UI markers round-trip as-is. */
export async function useUpsertMeasurementAnnotation(
  id: string,
  descriptions: FhirCdaDescriptions,
): Promise<MeasurementAnnotationResponse> {
  const res = await dtApi.put<{ descriptions: FhirCdaDescriptions }>(`${fhirBase(id)}/annotation`, { descriptions });
  return { id, measurementId: id, annotationId: "", descriptions: res.descriptions, createdAt: "", updatedAt: "" };
}

/**
 * Approval: commit a staged (or failed) upload to MinIO + Postgres, then push
 * its annotation to FHIR. Returns immediately (the server works in the
 * background); poll `useGetMeasurement` for the outcome.
 */
export async function useMeasurementSubmit(id: string): Promise<MeasurementResponse> {
  const { kind, rawId } = splitMeasurementId(id);
  if (kind === "dataset") await dtApi.post(`/datasets/${rawId}/fhir/push`, {});
  else await dtApi.post(`/datasets/uploads/${rawId}/approve`, {});
  return useGetMeasurement(id);
}

/** Re-push a committed dataset's annotation to FHIR (idempotent). */
export async function useMeasurementRetryFhir(id: string): Promise<MeasurementResponse> {
  const { rawId } = splitMeasurementId(id);
  await dtApi.post(`/datasets/${rawId}/fhir/push`, {});
  return useGetMeasurement(id);
}

/**
 * fhir.json for the Preview page / Export: the pushed bundle once completed,
 * otherwise a dry-run build (UUIDs are placeholders until approval).
 */
export async function useMeasurementFhirPreview(id: string): Promise<Record<string, any>> {
  return dtApi.get<Record<string, any>>(`${fhirBase(id)}/preview`);
}

/** Delete an upload (not yet committed) or a committed dataset (MinIO, Postgres, FHIR). */
export async function useDeleteMeasurement(id: string): Promise<MeasurementDeleteResponse> {
  const { kind, rawId } = splitMeasurementId(id);
  if (kind === "dataset") await dtApi.delete(`/datasets/${rawId}`);
  else await dtApi.delete(`/datasets/uploads/${rawId}`);
  return { status: true, message: "Measurement deleted." };
}

// ---------------------------------------------------------------------------
// Chunked upload — control-plane endpoints.
//
// The part PUTs are NOT here: they send raw octet-stream bytes and live in
// `measurement_upload.ts`, which calls the interceptor-bearing dtApiAxios
// instance directly so a mid-upload 401 still triggers the keycloak refresh.
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

/** Create an upload session, staged for annotation + Approval before commit. */
export async function useUploadInit(payload: UploadInitPayload): Promise<UploadInitResponse> {
  const res = await dtApi.post<{ uploadId: string; maxPartSize: number }>(`/datasets/uploads`, {
    ...payload,
    category: "measurements",
    commitMode: "on_approve",
  });
  return { measurementId: `upload:${res.uploadId}`, maxPartSize: res.maxPartSize };
}

/** Received parts, for resume. Rejects with 404 once the session stopped receiving. */
export async function useUploadStatus(id: string): Promise<UploadStatusResponse> {
  const session = await dtApi.get<UploadSession>(`/datasets/uploads/${splitMeasurementId(id).rawId}`);
  if (!session.upload) {
    throw Object.assign(new Error("Upload is no longer receiving parts"), { response: { status: 404 } });
  }
  return session.upload;
}

/** Assemble + validate + stage the upload; returns it as a `pending` measurement. */
export async function useUploadFinalize(id: string): Promise<MeasurementResponse> {
  await dtApi.post(`/datasets/uploads/${splitMeasurementId(id).rawId}/finalize`, {});
  return useGetMeasurement(id);
}

/** Abort an upload: drop its parts / staged files and the session. */
export async function useUploadCancel(id: string): Promise<{ success: boolean; id: string }> {
  await dtApi.delete(`/datasets/uploads/${splitMeasurementId(id).rawId}`);
  return { success: true, id };
}
