import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
const { toastError, deleteWorkflow, deleteTool } = vi.hoisted(() => ({ toastError: vi.fn(), deleteWorkflow: vi.fn(), deleteTool: vi.fn() }));
vi.mock("@/bootstrap/tool_api", () => ({
  useDeleteTool: deleteTool, useToolApprovalStatus: vi.fn(),
}));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: toastError, warning: vi.fn(), success: vi.fn() }) }));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowApprovalStatus: vi.fn(), useDeleteWorkflow: deleteWorkflow }));

import CardUI from "../CardUI.vue";
import WorkflowCard from "../WorkflowCard.vue";
import ToolCard from "../ToolCard.vue";
import MeasurementCard from "../../measurements/components/MeasurementCard.vue";
import ModelCard from "../../models/components/ModelCard.vue";

const plugins = [testVuetify()];
const menu = (w: ReturnType<typeof mount>) => w.findComponent(CardUI).props("menuItems") as { label: string; onClick: () => void }[];
/** The card's tags, in order. */
const chips = (w: ReturnType<typeof mount>) => w.findAll(".aurora-chip").map((c) => c.text());
const chip = (w: ReturnType<typeof mount>, label: string) => w.findAll(".aurora-chip").find((c) => c.text() === label)!;

const WORKFLOW = { id: "p1", name: "portal wf", version: "1", repositoryUrl: "", status: "completed", createdAt: "", updatedAt: "" };
const PLATFORM_WORKFLOW = { ...WORKFLOW, id: "wf-1", uuid: "wf-1", name: "workflow_image_conversion", version: "", platformOnly: true,
  workflowType: "script" };
const TOOL = { id: "t1", name: "portal tool", label: "Script", status: "completed", createdAt: "", updatedAt: "" };
const PLATFORM_TOOL = { ...TOOL, id: "t-9", uuid: "t-9", name: "tool_dicom_to_nifti", platformOnly: true };
const WORKFLOW_TOOL = { ...TOOL, id: "w1", label: "GUI", kind: "workflow", workflowName: "workflow_volview",
  name: "tool_volview", uuid: "tool-v" };

describe("WorkflowCard", () => {
  it("offers only delete for a platform workflow, and shows where it came from", () => {
    const w = mount(WorkflowCard, { props: { workflow: PLATFORM_WORKFLOW as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Delete workflow"]);
    // Uploaded through the API: in platform like any other, and never built by the portal.
    expect(chips(w)).toEqual(["in platform", "script"]);
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_WORKFLOW]);
    expect(w.emitted("delete")).toBeUndefined();
  });

  it("tags a workflow approved into the platform, like the Tool Hub", () => {
    const registration = (workflow: object) =>
      chips(mount(WorkflowCard, { props: { workflow: workflow as any }, global: { plugins } }))[0];

    expect(registration({ ...WORKFLOW, uuid: "a8d6da0e-1" })).toBe("in platform");
    expect(registration(WORKFLOW)).toBe("draft");
    // The legacy approval only gives the row a placeholder; it never reached the platform.
    expect(registration({ ...WORKFLOW, uuid: "sparc-workflow-$x" })).toBe("draft");
    expect(registration({ ...WORKFLOW, handoffStatus: "committing" })).toBe("registering…");
  });

  it("orders its tags registration, build, type, then descriptive ones", () => {
    const wf = { ...WORKFLOW, workflowType: "gui", author: "ann", createdAt: "2026-10-01T10:00:00" };
    const w = mount(WorkflowCard, { props: { workflow: wf as any }, global: { plugins } });

    expect(chips(w).slice(0, 5)).toEqual(["draft", "build · completed", "gui", "v1", "ann"]);
    expect(chips(w)).toHaveLength(6);
  });

  it("explains a failed approval or FHIR push on hover", () => {
    const tag = (workflow: object, label: string) =>
      chip(mount(WorkflowCard, { props: { workflow: workflow as any }, global: { plugins } }), label);

    expect(tag({ ...WORKFLOW, handoffStatus: "failed", handoffError: "SEEK 403" }, "registration failed")
      .attributes("title")).toBe("SEEK 403");
    expect(tag({ ...WORKFLOW, uuid: "a1", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" }, "in platform")
      .attributes("title")).toBe("FHIR publishing failed: HAPI 500");
  });

  it("keeps the portal workflow menu, and asks the hub to delete", async () => {
    const w = mount(WorkflowCard, { props: { workflow: WORKFLOW as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Submit to approval", "Delete workflow"]);
    menu(w)[1].onClick();
    await w.vm.$nextTick();
    // The hub confirms and deletes; the card calls nothing itself.
    expect(w.emitted("delete")?.[0]).toEqual([WORKFLOW]);
    expect(deleteWorkflow).not.toHaveBeenCalled();
    expect(w.find(".ucard--disabled").exists()).toBe(false);
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

describe("WorkflowCard DAG deploy", () => {
  const mountWf = (workflow: object, canDeploy = true) =>
    mount(WorkflowCard, { props: { workflow: workflow as any, canDeploy }, global: { plugins } });

  it("offers an admin Deploy DAG for a script workflow in the platform", () => {
    const w = mountWf(PLATFORM_WORKFLOW);

    expect(menu(w).map((m) => m.label)).toEqual(["Deploy DAG", "Delete workflow"]);
    menu(w)[0].onClick();
    expect(w.emitted("deploy-dag")?.[0]).toEqual([PLATFORM_WORKFLOW]);
  });

  it("offers it for a portal script workflow once it is approved into the platform", () => {
    const approved = { ...WORKFLOW, uuid: "a8d6da0e-1", workflowType: "script", isSds: true };

    expect(menu(mountWf(approved)).map((m) => m.label)).toEqual(["Submit to approval", "Deploy DAG", "Delete workflow"]);
  });

  it("does not offer it to a non-admin, for other workflow types, before registration, or while deploying", () => {
    const labels = (workflow: object, canDeploy = true) => menu(mountWf(workflow, canDeploy)).map((m) => m.label);

    expect(labels(PLATFORM_WORKFLOW, false)).not.toContain("Deploy DAG");
    expect(labels({ ...PLATFORM_WORKFLOW, workflowType: "gui" })).not.toContain("Deploy DAG");
    expect(labels({ ...WORKFLOW, workflowType: "script" })).not.toContain("Deploy DAG");
    expect(labels({ ...WORKFLOW, workflowType: "script", uuid: "sparc-workflow-$x" })).not.toContain("Deploy DAG");
    expect(labels({ ...PLATFORM_WORKFLOW, dagStatus: "deploying" })).not.toContain("Deploy DAG");
  });

  it("tags the deploy status after build, with the failure on hover", () => {
    const wf = { ...WORKFLOW, uuid: "a8d6da0e-1", workflowType: "script", dagStatus: "failed", dagError: "ImportError" };
    const w = mountWf(wf, false);

    expect(chips(w).slice(0, 4)).toEqual(["in platform", "build · completed", "deploy · failed", "script"]);
    expect(chip(w, "deploy · failed").attributes("title")).toBe("ImportError");
  });
});

describe("ToolCard", () => {
  it("offers only delete for a platform tool", () => {
    const w = mount(ToolCard, { props: { tool: PLATFORM_TOOL as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Delete tool"]);
    expect(chips(w)).toEqual(["in platform", "script"]);
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_TOOL]);
    expect(w.emitted("delete")).toBeUndefined();
  });

  it("keeps the portal tool menu, and asks the hub to delete", () => {
    const w = mount(ToolCard, { props: { tool: TOOL as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Rebuild tool", "Submit to approval", "Delete tool"]);
    menu(w)[2].onClick();
    expect(w.emitted("delete")?.[0]).toEqual([TOOL]);
    expect(deleteTool).not.toHaveBeenCalled();
  });

  it("tags each tool type in one vocabulary", () => {
    for (const [label, type] of [["GUI", "gui"], ["Script", "script"], ["Notebook", "notebook"]]) {
      for (const tool of [{ ...TOOL, label }, { ...PLATFORM_TOOL, label }]) {
        expect(chips(mount(ToolCard, { props: { tool: tool as any }, global: { plugins } }))).toContain(type);
      }
    }
  });

  it("orders its tags registration, build, deploy, type, then descriptive ones", () => {
    const tool = { ...TOOL, label: "GUI", uuid: "a1", version: "2", author: "ann", hasBackend: true,
      deployStatus: "completed", status: "completed" };
    const w = mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

    expect(chips(w)).toEqual(["in platform", "build · completed", "deploy · completed", "gui", "v2", "ann"]);
  });

  it("shows a running build and a running approval", () => {
    const w = mount(ToolCard, { props: { tool: { ...TOOL, status: "building", handoffStatus: "uploading" } as any },
      global: { plugins } });

    expect(chips(w).slice(0, 2)).toEqual(["registering…", "build · building"]);
    expect(w.text()).not.toContain("approving");
  });

  it("tags a gui workflow's tool with its workflow, which owns rebuild, approval and delete", () => {
    const w = mount(ToolCard, { props: { tool: WORKFLOW_TOOL as any }, global: { plugins } });

    expect(chips(w)).toEqual(["in platform", "build · completed", "gui", "from workflow workflow_volview"]);
    expect(menu(w)).toEqual([]);
    const launch = w.findAll("button").find((b) => b.text().includes("Launch"))!;
    expect(launch.attributes("disabled")).toBeUndefined();
  });

  it("only stops a workflow tool's backend, like a tool's: Launch starts it", () => {
    const tool = { ...WORKFLOW_TOOL, hasBackend: true, deployStatus: "completed", latestDeployId: "d1", latestBuildId: "b1" };
    const w = mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

    expect(menu(w).map((m) => m.label)).toEqual(["Stop backend", "View logs"]);
    menu(w)[0].onClick();
    expect(w.emitted("compose-down")?.[0]).toEqual(["d1"]);

    const gui = { ...TOOL, label: "GUI", hasBackend: true, deployStatus: "completed", latestDeployId: "d2" };
    expect(menu(mount(ToolCard, { props: { tool: gui as any }, global: { plugins } })).map((m) => m.label))
      .toEqual(["Rebuild tool", "Submit to approval", "Stop backend", "View logs", "Delete tool"]);
  });

  it("launches a GUI tool whose backend is down: /tool-view starts it", async () => {
    const tool = { ...TOOL, label: "GUI", hasBackend: true, deployStatus: "completed", latestDeployId: "d1" };
    const w = mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

    await w.findAll("button").find((b) => b.text().includes("Launch"))!.trigger("click");
    expect(w.emitted("launch")?.[0]).toEqual(["t1"]);
  });
});

const measurement = (status: string, extra: object = {}) =>
  ({ id: "upload:m1", name: "m1", status, createdAt: "", updatedAt: "", ...extra });

describe("MeasurementCard", () => {
  const mountCard = (m: object) => mount(MeasurementCard, { props: { measurement: m as any }, global: { plugins } });

  it("asks the hub to delete, and stays as it is until the hub has deleted it", async () => {
    const w = mountCard(measurement("pending", { hasAnnotation: true }));
    menu(w).find((m) => m.label === "Delete measurement")!.onClick();
    await w.vm.$nextTick();
    expect(w.emitted("delete")?.[0]).toEqual([measurement("pending", { hasAnnotation: true })]);
    expect(w.find(".ucard--disabled").exists()).toBe(false);
  });

  it("shows only the registration tag through the lifecycle", () => {
    expect(chips(mountCard(measurement("pending_upload")))).toEqual(["upload paused"]);
    expect(chips(mountCard(measurement("pending", { hasAnnotation: true })))).toEqual(["draft"]);
    expect(chips(mountCard(measurement("uploading")))).toEqual(["registering…"]);
    expect(chips(mountCard(measurement("completed", { uuid: "d1" })))).toEqual(["in platform"]);
    expect(chips(mountCard(measurement("uploading", { uuid: "d1" })))).toEqual(["in platform"]);
  });

  it("explains a failure on hover instead of a stage tag", () => {
    const failed = mountCard(measurement("submit_failed", { failureStage: "upload", failureMessage: "disk full" }));
    expect(chips(failed)).toEqual(["registration failed"]);
    expect(chip(failed, "registration failed").attributes("title")).toBe("disk full");

    const fhir = mountCard(measurement("fhir_failed", { uuid: "d1", failureStage: "fhir_push", failureMessage: "HAPI 500" }));
    expect(chips(fhir)).toEqual(["in platform"]);
    expect(chip(fhir, "in platform").attributes("title")).toBe("FHIR publishing failed: HAPI 500");
    expect(fhir.text()).toContain("Retry FHIR");
  });
});

describe("ModelCard", () => {
  const mountCard = (m: object) => mount(ModelCard, { props: { model: m as any }, global: { plugins } });

  it("uses the measurement vocabulary, with no FHIR tag", () => {
    expect(chips(mountCard(measurement("pending_upload")))).toEqual(["upload paused"]);
    expect(chips(mountCard(measurement("pending", { hasAnnotation: true })))).toEqual(["draft"]);
    expect(chips(mountCard(measurement("uploading")))).toEqual(["registering…"]);
    expect(chips(mountCard(measurement("completed", { uuid: "d1", hasAnnotation: true })))).toEqual(["in platform"]);
  });

  it("explains a failure on hover, not inline", () => {
    const failed = mountCard(measurement("submit_failed", { failureMessage: "disk full" }));
    expect(chip(failed, "registration failed").attributes("title")).toBe("disk full");
    expect(failed.text()).not.toContain("disk full");

    const fhir = mountCard(measurement("fhir_failed", { uuid: "d1", failureMessage: "HAPI 500" }));
    expect(chip(fhir, "in platform").attributes("title")).toBe("FHIR publishing failed: HAPI 500");
    expect(fhir.text()).not.toContain("HAPI 500");
  });
});
