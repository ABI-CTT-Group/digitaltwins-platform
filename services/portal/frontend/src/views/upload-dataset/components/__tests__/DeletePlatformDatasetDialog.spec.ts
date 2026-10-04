import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useWorkflowTools: vi.fn(), deletePlatformDataset: vi.fn() }));
vi.mock("@/bootstrap/platform_api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/bootstrap/platform_api")>()),
  ...api,
}));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));

import DeletePlatformDatasetDialog from "../DeletePlatformDatasetDialog.vue";

const TOOLS = [
  { datasetUuid: "t-1", datasetName: "tool_dicom_to_nifti", seekId: "70", stepIds: ["dicom_to_nifti"] },
  { datasetUuid: "t-2", datasetName: "tool_dicom_to_nrrd", seekId: "71", stepIds: ["dicom_to_nrrd"] },
];

let wrapper: ReturnType<typeof mount> | undefined;

async function open(kind: "workflow" | "tool", item = { uuid: "wf-1", name: "workflow_image_conversion" }) {
  wrapper = mount(DeletePlatformDatasetDialog, {
    props: { kind, item, modelValue: true },
    global: { plugins: [testVuetify()] },
    attachTo: document.body,
  });
  await flushPromises();
  return wrapper;
}

const button = (testid: string) => document.querySelector<HTMLButtonElement>(`[data-testid="${testid}"]`);
const text = () => document.body.textContent ?? "";

beforeEach(() => vi.resetAllMocks());
afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = "";
});

describe("DeletePlatformDatasetDialog: workflow", () => {
  it("lists the workflow's tools and deletes it with them", async () => {
    api.useWorkflowTools.mockResolvedValue(TOOLS);
    api.deletePlatformDataset.mockResolvedValue({ toolsDeleted: ["t-1", "t-2"] });
    const w = await open("workflow");

    expect(api.useWorkflowTools).toHaveBeenCalledWith("wf-1");
    expect(text()).toContain("tool_dicom_to_nifti");
    expect(text()).toContain("tool_dicom_to_nrrd");
    expect(button("delete-with-tools")?.textContent).toContain("2 tools");

    button("delete-with-tools")!.click();
    await flushPromises();

    expect(api.deletePlatformDataset).toHaveBeenCalledWith("wf-1", true);
    expect(w.emitted("deleted")).toHaveLength(1);
  });

  it("can keep the tools", async () => {
    api.useWorkflowTools.mockResolvedValue(TOOLS);
    api.deletePlatformDataset.mockResolvedValue({ toolsDeleted: [] });
    const w = await open("workflow");

    button("delete-workflow-only")!.click();
    await flushPromises();

    expect(api.deletePlatformDataset).toHaveBeenCalledWith("wf-1", false);
    expect(w.emitted("deleted")).toHaveLength(1);
  });

  it("offers a plain delete for a workflow without tools", async () => {
    api.useWorkflowTools.mockResolvedValue([]);
    await open("workflow");

    expect(button("delete-with-tools")).toBeNull();
    expect(button("delete-workflow-only")?.textContent).toContain("Delete workflow");
  });

  it("does nothing until confirmed", async () => {
    api.useWorkflowTools.mockResolvedValue(TOOLS);
    const w = await open("workflow");

    button("cancel")!.click();
    await flushPromises();

    expect(api.deletePlatformDataset).not.toHaveBeenCalled();
    expect(w.emitted("deleted")).toBeUndefined();
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual([false]);
  });
});

describe("DeletePlatformDatasetDialog: tool", () => {
  it("deletes the tool once confirmed", async () => {
    api.deletePlatformDataset.mockResolvedValue({ toolsDeleted: [] });
    const w = await open("tool", { uuid: "t-9", name: "tool_volview" });

    expect(api.useWorkflowTools).not.toHaveBeenCalled();
    button("delete-tool")!.click();
    await flushPromises();

    expect(api.deletePlatformDataset).toHaveBeenCalledWith("t-9", undefined);
    expect(w.emitted("deleted")).toHaveLength(1);
  });

  it("keeps a tool a workflow still runs and says which workflow", async () => {
    api.deletePlatformDataset.mockRejectedValue({ response: { status: 409, data: { detail: {
      message: "used", workflows: [{ dataset_uuid: "wf-1", dataset_name: "workflow_image_conversion" }] } } } });
    const w = await open("tool", { uuid: "t-1", name: "tool_dicom_to_nifti" });

    button("delete-tool")!.click();
    await flushPromises();

    expect(text()).toContain("Used by workflow(s): workflow_image_conversion");
    expect(w.emitted("deleted")).toBeUndefined();
  });

  it("shows other errors", async () => {
    api.deletePlatformDataset.mockRejectedValue({ response: { status: 500, data: { detail: "Storage deletion failed" } } });
    const w = await open("tool", { uuid: "t-1", name: "tool_dicom_to_nifti" });

    button("delete-tool")!.click();
    await flushPromises();

    expect(text()).toContain("Storage deletion failed");
    expect(w.emitted("deleted")).toBeUndefined();
  });
});
