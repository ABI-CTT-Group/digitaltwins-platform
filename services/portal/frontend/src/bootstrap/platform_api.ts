/**
 * Datasets uploaded to the platform directly (platform API REST, CLI), which
 * no portal record produced: listing platform workflows, deleting platform
 * workflows / tools, and deploying any registered script workflow's DAG.
 * Portal-built ones keep using the builder otherwise.
 */
import { dtApi } from "./http";
import type { PlatformLink, WorkflowResponse } from "@/models/types";

/** A ``workflows`` row of GET /api/datasets (keys camelCased by the interceptor). */
interface PlatformWorkflowDataset {
  datasetUuid: string;
  datasetName?: string;
  workflowType?: string | null;
  fhirStatus?: string;
  fhirFailureMessage?: string;
  dagStatus?: string | null;
  dagError?: string | null;
  createdAt?: string;
}

const WORKFLOW_TYPES = new Set(["script", "notebook", "gui"]);

/** The portal's workflows, each with its platform dataset's FHIR status, then the platform
 *  workflow definitions the portal does not know. Assay workspace outputs share the category
 *  but have no ``workflowType``. */
export async function withPlatformWorkflows(workflows: WorkflowResponse[]): Promise<WorkflowResponse[]> {
  const res = await dtApi.get<{ datasets: PlatformWorkflowDataset[] }>("/datasets", { categories: "workflows" });
  const datasets = new Map((res.datasets ?? []).map((d) => [d.datasetUuid, d]));
  const known = workflows.map((w) => {
    const d = w.uuid ? datasets.get(w.uuid) : undefined;
    return d
      ? { ...w, fhirStatus: d.fhirStatus, fhirFailureMessage: d.fhirFailureMessage, dagStatus: d.dagStatus, dagError: d.dagError }
      : w;
  });
  const knownUuids = new Set(workflows.map((w) => w.uuid));
  const platform = [...datasets.values()]
    .filter((d) => !knownUuids.has(d.datasetUuid) && WORKFLOW_TYPES.has(d.workflowType ?? ""))
    .map((d) => ({
      id: d.datasetUuid, uuid: d.datasetUuid, name: d.datasetName || d.datasetUuid, version: "", repositoryUrl: "",
      description: "Uploaded to the platform directly.", status: "completed", platformOnly: true,
      workflowType: d.workflowType ?? undefined, fhirStatus: d.fhirStatus, fhirFailureMessage: d.fhirFailureMessage,
      dagStatus: d.dagStatus, dagError: d.dagError,
      createdAt: d.createdAt ?? "", updatedAt: d.createdAt ?? "",
    }));
  return [...known, ...platform];
}

/** The tool datasets a platform workflow's steps run. */
export async function useWorkflowTools(uuid: string): Promise<PlatformLink[]> {
  const res = await dtApi.get<{ workflowType: string | null; tools: PlatformLink[] }>(`/datasets/${uuid}/workflow-tools`);
  return res.tools ?? [];
}

/** DELETE a platform dataset; for a workflow, ``deleteTools`` says whether its tools go too. */
export async function deletePlatformDataset(uuid: string, deleteTools?: boolean) {
  return dtApi.delete(`/datasets/${uuid}`, deleteTools === undefined ? undefined : { deleteTools });
}

/** Deploy a registered script workflow's DAG into Airflow (admin only); resolves once Airflow
 *  has loaded it or reported why not. */
export async function deployWorkflowDag(uuid: string) {
  return dtApi.post<{ dagId: string; dagStatus: string; dagError: string | null }>(`/workflows/${uuid}/deploy`);
}

interface RawLink {
  dataset_uuid: string;
  dataset_name?: string;
  seek_id?: string;
  step_ids?: string[];
}

const link = (l: RawLink): PlatformLink => {
  const out: PlatformLink = { datasetUuid: l.dataset_uuid, datasetName: l.dataset_name };
  if (l.seek_id !== undefined) out.seekId = l.seek_id;
  if (l.step_ids !== undefined) out.stepIds = l.step_ids;
  return out;
};

/** The API's 409 for a delete it refused (a tool a workflow still runs, or a workflow without
 *  ``delete_tools``), else null. Error bodies are not camelCased by the interceptor. */
export function datasetInUse(err: unknown): { message: string; tools: PlatformLink[]; workflows: PlatformLink[] } | null {
  const response = (err as { response?: { status?: number; data?: { detail?: any } } })?.response;
  const detail = response?.status === 409 ? response.data?.detail : undefined;
  if (!detail || typeof detail !== "object") return null;
  return {
    message: String(detail.message ?? ""),
    tools: (detail.tools ?? []).map(link),
    workflows: (detail.workflows ?? []).map(link),
  };
}
