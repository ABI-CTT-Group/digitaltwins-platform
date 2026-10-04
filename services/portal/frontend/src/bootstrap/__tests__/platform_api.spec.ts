import { beforeEach, describe, expect, it, vi } from "vitest";

const dtApi = vi.hoisted(() => ({ get: vi.fn(), delete: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi }));

import {
  datasetInUse,
  deletePlatformDataset,
  usePlatformWorkflows,
  useWorkflowTools,
} from "@/bootstrap/platform_api";

beforeEach(() => vi.resetAllMocks());

describe("usePlatformWorkflows", () => {
  it("lists workflow definitions, not other workflows-category datasets or ones the portal knows", async () => {
    dtApi.get.mockResolvedValue({
      datasets: [
        { datasetUuid: "wf-1", datasetName: "workflow_image_conversion", workflowType: "script", seekId: "72",
          createdAt: "2026-10-02T10:00:00" },
        { datasetUuid: "assay-out", datasetName: "outputs", workflowType: null },
        { datasetUuid: "wf-known", datasetName: "known", workflowType: "gui" },
        { datasetUuid: "wf-2", workflowType: "gui" },
      ],
    });

    const workflows = await usePlatformWorkflows(new Set(["wf-known"]));

    expect(dtApi.get).toHaveBeenCalledWith("/datasets", { categories: "workflows" });
    expect(workflows.map((w) => w.id)).toEqual(["wf-1", "wf-2"]);
    expect(workflows[0]).toMatchObject({
      id: "wf-1", uuid: "wf-1", name: "workflow_image_conversion", status: "completed", platformOnly: true,
      workflowType: "script", description: "Uploaded to the platform directly.",
      createdAt: "2026-10-02T10:00:00", updatedAt: "2026-10-02T10:00:00",
    });
    expect(workflows[1].name).toBe("wf-2");
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
