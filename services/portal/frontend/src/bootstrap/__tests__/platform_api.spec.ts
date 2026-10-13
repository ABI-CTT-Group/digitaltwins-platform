import { beforeEach, describe, expect, it, vi } from "vitest";

const dtApi = vi.hoisted(() => ({ get: vi.fn(), delete: vi.fn(), post: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi }));

import {
  datasetInUse,
  deletePlatformDataset,
  deployWorkflowDag,
  withPlatformWorkflows,
  useWorkflowTools,
} from "@/bootstrap/platform_api";

beforeEach(() => vi.resetAllMocks());

describe("withPlatformWorkflows", () => {
  const portal = (id: string, uuid?: string) => ({ id, name: id, version: "1", repositoryUrl: "", status: "completed",
    createdAt: "", updatedAt: "", uuid });

  it("appends workflow definitions the portal does not know, not other workflows-category datasets", async () => {
    dtApi.get.mockResolvedValue({
      datasets: [
        { datasetUuid: "wf-1", datasetName: "workflow_image_conversion", workflowType: "script", seekId: "72",
          fhirStatus: "completed", createdAt: "2026-10-02T10:00:00" },
        { datasetUuid: "assay-out", datasetName: "outputs", workflowType: null },
        { datasetUuid: "wf-known", datasetName: "known", workflowType: "gui" },
        { datasetUuid: "wf-2", workflowType: "gui" },
      ],
    });

    const workflows = await withPlatformWorkflows([portal("p1", "wf-known")]);

    expect(dtApi.get).toHaveBeenCalledWith("/datasets", { categories: "workflows" });
    expect(workflows.map((w) => w.id)).toEqual(["p1", "wf-1", "wf-2"]);
    expect(workflows[1]).toMatchObject({
      id: "wf-1", uuid: "wf-1", name: "workflow_image_conversion", status: "completed", platformOnly: true,
      workflowType: "script", description: "Uploaded to the platform directly.", fhirStatus: "completed",
      createdAt: "2026-10-02T10:00:00", updatedAt: "2026-10-02T10:00:00",
    });
    expect(workflows[2].name).toBe("wf-2");
  });

  it("gives an approved portal workflow its platform dataset's FHIR status", async () => {
    dtApi.get.mockResolvedValue({
      datasets: [{ datasetUuid: "wf-a", workflowType: "script", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" }],
    });

    const [approved, draft] = await withPlatformWorkflows([portal("p1", "wf-a"), portal("p2")]);

    expect(approved).toMatchObject({ id: "p1", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" });
    expect(draft.fhirStatus).toBeUndefined();
  });
});

describe("DAG deploy status", () => {
  it("is carried onto portal and platform-only workflows", async () => {
    dtApi.get.mockResolvedValue({
      datasets: [
        { datasetUuid: "wf-a", workflowType: "script", dagStatus: "failed", dagError: "ImportError" },
        { datasetUuid: "wf-b", workflowType: "script", dagStatus: "deployed", dagError: null },
      ],
    });

    const [approved, platform] = await withPlatformWorkflows([{ id: "p1", name: "p1", version: "1",
      repositoryUrl: "", status: "completed", createdAt: "", updatedAt: "", uuid: "wf-a" }]);

    expect(approved).toMatchObject({ id: "p1", dagStatus: "failed", dagError: "ImportError" });
    expect(platform).toMatchObject({ id: "wf-b", dagStatus: "deployed", dagError: null });
  });

  it("deploys through the platform API", async () => {
    dtApi.post.mockResolvedValue({ dagId: "workflow_72", dagStatus: "deployed", dagError: null });

    expect(await deployWorkflowDag("wf-b")).toEqual({ dagId: "workflow_72", dagStatus: "deployed", dagError: null });
    expect(dtApi.post).toHaveBeenCalledWith("/workflows/wf-b/deploy");
  });
});

describe("useWorkflowTools", () => {
  it("reads the workflow's tool datasets", async () => {
    const tools = [{ datasetUuid: "t-1", datasetName: "tool_a", seekId: "70", stepIds: ["a"] }];
    dtApi.get.mockResolvedValue({ workflowType: "script", tools });

    expect(await useWorkflowTools("wf-1")).toEqual(tools);
    expect(dtApi.get).toHaveBeenCalledWith("/datasets/wf-1/workflow-tools");
  });
});

describe("deletePlatformDataset", () => {
  it("sends delete_tools only when it is given", async () => {
    dtApi.delete.mockResolvedValue({ toolsDeleted: [] });

    await deletePlatformDataset("tool-1");
    await deletePlatformDataset("wf-1", true);
    await deletePlatformDataset("wf-1", false);

    expect(dtApi.delete.mock.calls).toEqual([
      ["/datasets/tool-1", undefined],
      ["/datasets/wf-1", { deleteTools: true }],
      ["/datasets/wf-1", { deleteTools: false }],
    ]);
  });
});

describe("datasetInUse", () => {
  const conflict = (detail: unknown) => ({ isAxiosError: true, response: { status: 409, data: { detail } } });

  it("reads the workflows that still use a tool (error bodies keep the API's snake_case)", () => {
    const err = conflict({ message: "Tool dataset 't-1' is used by workflow(s): wf", workflows: [
      { dataset_uuid: "wf-1", dataset_name: "workflow_image_conversion" }] });

    expect(datasetInUse(err)).toEqual({
      message: "Tool dataset 't-1' is used by workflow(s): wf",
      workflows: [{ datasetUuid: "wf-1", datasetName: "workflow_image_conversion" }],
      tools: [],
    });
  });

  it("reads a workflow's tools", () => {
    const err = conflict({ message: "pass delete_tools", tools: [
      { dataset_uuid: "t-1", dataset_name: "tool_a", seek_id: "70", step_ids: ["a"] }] });

    expect(datasetInUse(err)?.tools).toEqual([{ datasetUuid: "t-1", datasetName: "tool_a", seekId: "70", stepIds: ["a"] }]);
  });

  it("is null for anything that is not a 409", () => {
    expect(datasetInUse({ response: { status: 500, data: {} } })).toBeNull();
    expect(datasetInUse(new Error("network"))).toBeNull();
  });
});
