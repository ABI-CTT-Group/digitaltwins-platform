import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({
  useSeekProjects: vi.fn(), useToolApproval: vi.fn(), useToolApprovalStatus: vi.fn(),
  usePlatformDataset: vi.fn(), useRetryToolFhir: vi.fn(),
  useWorkflowPlatformApproval: vi.fn(), useWorkflowApprovalStatus: vi.fn(),
}));
vi.mock("@/bootstrap/tool_api", () => ({
  useSeekProjects: api.useSeekProjects, useToolApproval: api.useToolApproval,
  useToolApprovalStatus: api.useToolApprovalStatus, usePlatformDataset: api.usePlatformDataset,
  useRetryToolFhir: api.useRetryToolFhir,
}));
vi.mock("@/bootstrap/workflow_api", () => ({
  useWorkflowPlatformApproval: api.useWorkflowPlatformApproval, useWorkflowApprovalStatus: api.useWorkflowApprovalStatus,
}));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn() }) }));

import ToolApprovalDialog from "../ToolApprovalDialog.vue";

const RUNNING = { buildId: "b1", handoffStatus: "uploading", partsSent: 0, partsTotal: 3 };
let wrapper: ReturnType<typeof mount> | undefined;

async function open(props: { item: any; kind?: "tool" | "workflow" }) {
  wrapper = mount(ToolApprovalDialog, {
    props: { modelValue: false, ...props } as any,
    global: { plugins: [testVuetify()] },
    attachTo: document.body,
  });
  await wrapper.setProps({ modelValue: true });
  await flushPromises();
}

const approveButton = () =>
  Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((b) => b.textContent?.trim() === "Approve")!;

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers();
  api.useSeekProjects.mockResolvedValue([{ id: 11, title: "P" }]);
  api.useToolApproval.mockResolvedValue(RUNNING);
  api.useWorkflowPlatformApproval.mockResolvedValue(RUNNING);
  api.useToolApprovalStatus.mockResolvedValue({ ...RUNNING, handoffStatus: "failed" });
  api.useWorkflowApprovalStatus.mockResolvedValue({ ...RUNNING, handoffStatus: "failed" });
});
afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("ToolApprovalDialog", () => {
  it("approves a workflow through the workflow endpoints", async () => {
    await open({ kind: "workflow", item: { id: "w1", name: "Convert", seekProjectId: 11 } });

    approveButton().click();
    await flushPromises();

    expect(api.useWorkflowPlatformApproval).toHaveBeenCalledWith("w1", { seekProjectId: 11, fhir: true });
    expect(api.useToolApproval).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(3000);
    expect(api.useWorkflowApprovalStatus).toHaveBeenCalledWith("w1");
    expect(api.useToolApprovalStatus).not.toHaveBeenCalled();
  });

  it("approves a tool by default", async () => {
    await open({ item: { id: "t1", name: "Tool", seekProjectId: 11 } });

    approveButton().click();
    await flushPromises();

    expect(api.useToolApproval).toHaveBeenCalledWith("t1", { seekProjectId: 11, fhir: true });
    expect(api.useWorkflowPlatformApproval).not.toHaveBeenCalled();
  });
});
