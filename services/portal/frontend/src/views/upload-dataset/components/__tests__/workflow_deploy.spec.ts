import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useWorkflowHub: vi.fn(), deployWorkflowDag: vi.fn() }));
const toast = vi.hoisted(() => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn() }));
const auth = vi.hoisted(() => ({ hasAdminRole: true }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({}));
vi.mock("@/bootstrap/platform_api", () => ({ deployWorkflowDag: api.deployWorkflowDag }));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowHub: api.useWorkflowHub }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => auth }));
vi.mock("vue-toastification", () => ({ useToast: () => toast }));

import WorkflowsOverallView from "../../workflow/WorkflowsOverallView.vue";
import WorkflowCard from "../WorkflowCard.vue";

const plugins = [testVuetify()];
const WF = { id: "wf-1", uuid: "wf-1", name: "image conversion", version: "", repositoryUrl: "", status: "completed",
  createdAt: "", updatedAt: "", platformOnly: true, workflowType: "script", dagStatus: "pending" };

async function hub() {
  const w = mount(WorkflowsOverallView, { global: { plugins } });
  await flushPromises();
  return w;
}

beforeEach(() => {
  vi.resetAllMocks();
  auth.hasAdminRole = true;
  api.useWorkflowHub.mockResolvedValue([{ ...WF }]);
});

describe("Workflow Hub DAG deploy", () => {
  it("lets only admins deploy", async () => {
    expect((await hub()).findComponent(WorkflowCard).props("canDeploy")).toBe(true);
    auth.hasAdminRole = false;
    expect((await hub()).findComponent(WorkflowCard).props("canDeploy")).toBe(false);
  });

  it("deploys through the platform API, shows it deploying, then reports and refreshes", async () => {
    let finish!: (v: unknown) => void;
    api.deployWorkflowDag.mockReturnValue(new Promise((r) => { finish = r; }));
    const w = await hub();

    w.findComponent(WorkflowCard).vm.$emit("deploy-dag", w.findComponent(WorkflowCard).props("workflow"));
    await flushPromises();
    expect(api.deployWorkflowDag).toHaveBeenCalledWith("wf-1");
    expect(w.findComponent(WorkflowCard).props("workflow")).toMatchObject({ dagStatus: "deploying" });

    finish({ dagId: "workflow_72", dagStatus: "deployed", dagError: null });
    await flushPromises();
    expect(toast.success).toHaveBeenCalledWith("DAG workflow_72 deployed to Airflow.");
    expect(api.useWorkflowHub).toHaveBeenCalledTimes(2);
  });

  it("shows why Airflow could not load the DAG", async () => {
    api.deployWorkflowDag.mockResolvedValue({ dagId: "workflow_72", dagStatus: "failed", dagError: "ImportError: x" });
    const w = await hub();

    w.findComponent(WorkflowCard).vm.$emit("deploy-dag", w.findComponent(WorkflowCard).props("workflow"));
    await flushPromises();
    expect(toast.error).toHaveBeenCalledWith("DAG deploy failed: ImportError: x");
  });

  it("shows the API's reason when it refuses the deploy", async () => {
    api.deployWorkflowDag.mockRejectedValue({ response: { status: 422, data: { detail: "dag_id must be ..." } } });
    const w = await hub();

    w.findComponent(WorkflowCard).vm.$emit("deploy-dag", w.findComponent(WorkflowCard).props("workflow"));
    await flushPromises();
    expect(toast.error).toHaveBeenCalledWith("DAG deploy failed: dag_id must be ...");
    expect(api.useWorkflowHub).toHaveBeenCalledTimes(2);
  });
});
