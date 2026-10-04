/**
 * Datasets uploaded to the platform directly (digitaltwins-api REST, CLI), which
 * no portal record produced: listing platform workflows, and deleting platform
 * workflows / tools. Portal-built ones keep using the portal backend.
 */
import { dtApi } from "./http";
import type { PlatformLink, WorkflowResponse } from "@/models/types";

/** A ``workflows`` row of GET /digitaltwins-api/datasets (keys camelCased by the interceptor). */
interface PlatformWorkflowDataset {
  datasetUuid: string;
  datasetName?: string;
  workflowType?: string | null;
  createdAt?: string;
}

const WORKFLOW_TYPES = new Set(["script", "notebook", "gui"]);

/** Platform workflow definitions the portal does not know (``known``: portal workflows' uuids).
 *  Assay workspace outputs share the category but have no ``workflowType``. */
export async function usePlatformWorkflows(known: Set<string>): Promise<WorkflowResponse[]> {
  const res = await dtApi.get<{ datasets: PlatformWorkflowDataset[] }>("/datasets", { categories: "workflows" });
  return (res.datasets ?? [])
    .filter((d) => !known.has(d.datasetUuid) && WORKFLOW_TYPES.has(d.workflowType ?? ""))
    .map((d) => ({
      id: d.datasetUuid, uuid: d.datasetUuid, name: d.datasetName || d.datasetUuid, version: "", repositoryUrl: "",
      description: "Uploaded to the platform directly.", status: "completed", platformOnly: true,
      workflowType: d.workflowType ?? undefined, createdAt: d.createdAt ?? "", updatedAt: d.createdAt ?? "",
    }));
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
