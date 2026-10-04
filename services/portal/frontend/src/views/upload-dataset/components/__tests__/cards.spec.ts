import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({
  useGetDockerComposeStatus: vi.fn(), useDeleteTool: vi.fn(), useToolApprovalStatus: vi.fn(),
}));
const { toastError, deleteWorkflow } = vi.hoisted(() => ({ toastError: vi.fn(), deleteWorkflow: vi.fn() }));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: toastError, warning: vi.fn(), success: vi.fn() }) }));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowApprovalStatus: vi.fn(), useDeleteWorkflow: deleteWorkflow }));

import CardUI from "../CardUI.vue";
import WorkflowCard from "../WorkflowCard.vue";
import ToolCard from "../ToolCard.vue";

const plugins = [testVuetify()];
const menu = (w: ReturnType<typeof mount>) => w.findComponent(CardUI).props("menuItems") as { label: string; onClick: () => void }[];

const WORKFLOW = { id: "p1", name: "portal wf", version: "1", repositoryUrl: "", status: "completed", createdAt: "", updatedAt: "" };
const PLATFORM_WORKFLOW = { ...WORKFLOW, id: "wf-1", uuid: "wf-1", name: "workflow_image_conversion", platformOnly: true,
  workflowType: "script" };
const TOOL = { id: "t1", name: "portal tool", label: "Script", status: "completed", createdAt: "", updatedAt: "" };
const PLATFORM_TOOL = { ...TOOL, id: "t-9", uuid: "t-9", name: "tool_dicom_to_nifti", platformOnly: true };
const WORKFLOW_TOOL = { ...TOOL, id: "w1", label: "GUI", kind: "workflow", workflowName: "workflow_volview",
  name: "tool_volview", uuid: "tool-v" };

describe("WorkflowCard", () => {
  it("offers only delete for a platform workflow, and shows where it came from", () => {
    const w = mount(WorkflowCard, { props: { workflow: PLATFORM_WORKFLOW as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Delete workflow"]);
    expect(w.text()).toContain("platform upload");
    expect(w.text()).toContain("script");
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_WORKFLOW]);
    expect(w.emitted("delete")).toBeUndefined();
  });

  it("tags a workflow approved into the platform, like the Tool Hub", () => {
    const tagged = (workflow: object) =>
      mount(WorkflowCard, { props: { workflow: workflow as any }, global: { plugins } }).text();

    expect(tagged({ ...WORKFLOW, uuid: "a8d6da0e-1" })).toContain("in platform");
    expect(tagged(WORKFLOW)).not.toContain("in platform");
    // The legacy approval only gives the row a placeholder; it never reached the platform.
    expect(tagged({ ...WORKFLOW, uuid: "sparc-workflow-$x" })).not.toContain("in platform");
    // A platform upload says so instead.
    expect(tagged(PLATFORM_WORKFLOW)).not.toContain("in platform");
  });

  it("keeps the portal workflow menu", async () => {
    const w = mount(WorkflowCard, { props: { workflow: WORKFLOW as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Submit to approval", "Delete workflow"]);
    deleteWorkflow.mockResolvedValue({ status: true, message: "ok" });
    await menu(w)[1].onClick();
    expect(deleteWorkflow).toHaveBeenCalledWith("p1");
    expect(w.emitted("delete")?.[0]).toEqual([{ status: true, message: "ok" }]);
  });

  it("shows the error and stops being busy when a workflow delete fails", async () => {
    const w = mount(WorkflowCard, { props: { workflow: WORKFLOW as any }, global: { plugins } });
    deleteWorkflow.mockResolvedValue({ status: false, message: "platform said no" });
    await menu(w)[1].onClick();
    expect(toastError).toHaveBeenCalledWith("Error: platform said no");
    expect(w.findComponent(CardUI).props("isDeleting")).toBe(false);

    deleteWorkflow.mockRejectedValue(new Error("403"));
    await menu(w)[1].onClick();
    expect(toastError).toHaveBeenCalledWith("Error: 403");
    expect(w.findComponent(CardUI).props("isDeleting")).toBe(false);
  });

  it("routes a portal SDS workflow to the platform approval", () => {
    const sds = { ...WORKFLOW, workflowType: "script", isSds: true };
    const w = mount(WorkflowCard, { props: { workflow: sds as any }, global: { plugins } });

    menu(w)[0].onClick();
    expect(w.emitted("approve-platform")?.[0]).toEqual([sds]);
    expect(w.emitted("submit-approve")).toBeUndefined();
  });

  it("keeps the legacy approval for a portal workflow without a type", () => {
    const w = mount(WorkflowCard, { props: { workflow: WORKFLOW as any }, global: { plugins } });

    menu(w)[0].onClick();
    expect(w.emitted("submit-approve")?.[0]).toEqual(["p1"]);
    expect(w.emitted("approve-platform")).toBeUndefined();
  });

  it("keeps the legacy approval for a typed workflow that is not an SDS package", () => {
    const rootCwl = { ...WORKFLOW, workflowType: "gui", isSds: false };
    const w = mount(WorkflowCard, { props: { workflow: rootCwl as any }, global: { plugins } });

    menu(w)[0].onClick();
    expect(w.emitted("submit-approve")?.[0]).toEqual(["p1"]);
    expect(w.emitted("approve-platform")).toBeUndefined();
  });
});

describe("ToolCard", () => {
  it("offers only delete for a platform tool", () => {
    const w = mount(ToolCard, { props: { tool: PLATFORM_TOOL as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Delete tool"]);
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_TOOL]);
    expect(w.emitted("delete")).toBeUndefined();
  });

  it("keeps the portal tool menu", () => {
    const w = mount(ToolCard, { props: { tool: TOOL as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Rebuild tool", "Submit to approval", "Delete tool"]);
  });

  it("tags a gui workflow's tool with its workflow, which owns rebuild, approval and delete", () => {
    const w = mount(ToolCard, { props: { tool: WORKFLOW_TOOL as any }, global: { plugins } });

    expect(w.text()).toContain("from workflow workflow_volview");
    expect(w.text()).not.toContain("in platform");
    expect(menu(w)).toEqual([]);
    const launch = w.findAll("button").find((b) => b.text().includes("Launch"))!;
    expect(launch.attributes("disabled")).toBeUndefined();
  });

  it("runs a workflow tool's backend like a tool's", () => {
    const tool = { ...WORKFLOW_TOOL, hasBackend: true, deployStatus: "completed", latestDeployId: "d1", latestBuildId: "b1" };
    const w = mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Deploy backend", "Compose up", "Compose down", "View logs"]);
    menu(w)[0].onClick();
    expect(w.emitted("deploy")?.[0]).toEqual(["w1", "workflow"]);
  });
});
