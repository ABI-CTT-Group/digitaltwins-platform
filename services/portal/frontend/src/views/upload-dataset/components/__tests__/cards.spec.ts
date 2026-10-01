import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({
  useGetDockerComposeStatus: vi.fn(), useDeleteTool: vi.fn(), useToolApprovalStatus: vi.fn(),
}));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn() }) }));

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

  it("keeps the portal workflow menu", () => {
    const w = mount(WorkflowCard, { props: { workflow: WORKFLOW as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Submit to approval", "Delete workflow"]);
    menu(w)[1].onClick();
    expect(w.emitted("delete")?.[0]).toEqual(["p1"]);
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
});
