import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
const { deleteWorkflow, deleteTool } = vi.hoisted(() => ({ deleteWorkflow: vi.fn(), deleteTool: vi.fn() }));
vi.mock("@/bootstrap/tool_api", () => ({ useDeleteTool: deleteTool, useToolApprovalStatus: vi.fn() }));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowApprovalStatus: vi.fn(), useDeleteWorkflow: deleteWorkflow }));

import CardUI from "../CardUI.vue";
import WorkflowCard from "../WorkflowCard.vue";
import ToolCard from "../ToolCard.vue";
import MeasurementCard from "../../measurements/components/MeasurementCard.vue";
import ModelCard from "../../models/components/ModelCard.vue";

const plugins = [testVuetify()];
type Wrapper = ReturnType<typeof mount>;
const menu = (w: Wrapper) => w.findComponent(CardUI).props("menuItems") as { label: string; onClick: () => void }[];
const labels = (w: Wrapper) => menu(w).map((m) => m.label);
const chips = (w: Wrapper) => w.findAll(".aurora-chip").map((c) => c.text());
const sentence = (w: Wrapper) => w.find(".status__sentence").text();
/** The card's one next-step button, if it has one. */
const action = (w: Wrapper) => w.find(".ucard__cta button");

const WORKFLOW = { id: "p1", name: "portal wf", version: "1", repositoryUrl: "", status: "completed", latestBuildId: "b1",
  workflowType: "script", isSds: true, createdAt: "", updatedAt: "" };
const APPROVED_WORKFLOW = { ...WORKFLOW, uuid: "a8d6da0e-1", handoffStatus: "completed" };
const PLATFORM_WORKFLOW = { ...WORKFLOW, id: "wf-1", uuid: "wf-1", name: "workflow_image_conversion", version: "",
  platformOnly: true, latestBuildId: undefined };
const TOOL = { id: "t1", name: "portal tool", label: "Script", status: "completed", latestBuildId: "b1", createdAt: "", updatedAt: "" };
const GUI_TOOL = { ...TOOL, label: "GUI", hasBackend: true };
const PLATFORM_TOOL = { ...TOOL, id: "t-9", uuid: "t-9", name: "tool_dicom_to_nifti", platformOnly: true, latestBuildId: undefined };
const WORKFLOW_TOOL = { ...GUI_TOOL, id: "w1", hasBackend: false, kind: "workflow", workflowName: "workflow_volview",
  name: "tool_volview", uuid: "tool-v" };

describe("WorkflowCard", () => {
  const mountWf = (workflow: object, canDeploy = false) =>
    mount(WorkflowCard, { props: { workflow: workflow as any, canDeploy }, global: { plugins } });

  it("says what state it is in and offers the next step", async () => {
    const w = mountWf(WORKFLOW);
    expect(sentence(w)).toBe("Built — not in the platform yet");
    expect(action(w).text()).toBe("Approve");
    await action(w).trigger("click");
    expect(w.emitted("approve-platform")?.[0]).toEqual([WORKFLOW]);
  });

  it("keeps chips for facts and problems only", () => {
    const wf = { ...APPROVED_WORKFLOW, author: "ann", createdAt: "2026-10-01T10:00:00", dagStatus: "failed", dagError: "ImportError" };
    const w = mountWf(wf);
    expect(chips(w)).toEqual(["script", "v1", "DAG deploy failed"]);
    expect(w.findAll(".aurora-chip")[2].attributes("title")).toBe("ImportError");
  });

  it("offers only delete for a platform workflow", () => {
    const w = mountWf(PLATFORM_WORKFLOW);
    expect(sentence(w)).toBe("In the platform");
    expect(labels(w)).toEqual(["Delete workflow"]);
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_WORKFLOW]);
    expect(w.emitted("delete")).toBeUndefined();
  });

  it("continues the registration of a workflow that was never built", async () => {
    const wf = { ...WORKFLOW, status: "pending", latestBuildId: undefined };
    const w = mountWf(wf);
    await action(w).trigger("click");
    expect(w.emitted("continue")?.[0]).toEqual([wf]);
  });

  it("adds or edits an SDS workflow's FHIR annotation until it is in the platform", () => {
    const w = mountWf(WORKFLOW);
    menu(w).find((m) => m.label === "Add FHIR annotation")!.onClick();
    expect(w.emitted("edit-annotation")?.[0]).toEqual([WORKFLOW]);
    expect(labels(mountWf({ ...WORKFLOW, hasAnnotation: true }))).toEqual(["Edit FHIR annotation", "Delete workflow"]);
    expect(labels(mountWf(APPROVED_WORKFLOW))).toEqual(["Delete workflow"]);
  });

  it("asks the hub to delete a portal workflow", async () => {
    const w = mountWf(WORKFLOW);
    expect(labels(w)).toEqual(["Add FHIR annotation", "Delete workflow"]);
    menu(w)[1].onClick();
    await w.vm.$nextTick();
    expect(w.emitted("delete")?.[0]).toEqual([WORKFLOW]);
    expect(deleteWorkflow).not.toHaveBeenCalled();
    expect(w.find(".ucard--disabled").exists()).toBe(false);
  });

  it("can't approve a legacy workflow that isn't an SDS package", () => {
    const w = mountWf({ ...WORKFLOW, isSds: false });
    expect(sentence(w)).toBe("Not an SDS package — not supported yet");
    expect(action(w).exists()).toBe(false);
    expect(labels(w)).toEqual(["Delete workflow"]);
  });

  it("lets an admin deploy a script workflow's DAG: the button, then the menu to redeploy", async () => {
    const notDeployed = mountWf({ ...APPROVED_WORKFLOW, dagStatus: null }, true);
    expect(action(notDeployed).text()).toBe("Deploy DAG");
    await action(notDeployed).trigger("click");
    expect(notDeployed.emitted("deploy-dag")).toHaveLength(1);
    expect(labels(notDeployed)).toEqual(["Delete workflow"]);

    const deployed = mountWf({ ...APPROVED_WORKFLOW, dagStatus: "deployed" }, true);
    expect(action(deployed).exists()).toBe(false);
    expect(labels(deployed)).toEqual(["Deploy DAG again", "Delete workflow"]);
    expect(labels(mountWf({ ...APPROVED_WORKFLOW, dagStatus: "deployed" }))).toEqual(["Delete workflow"]);
  });

  it("retries a failed FHIR push", async () => {
    const wf = { ...APPROVED_WORKFLOW, fhirStatus: "failed", fhirFailureMessage: "HAPI 500" };
    const w = mountWf(wf);
    expect(w.find(".status__detail").text()).toBe("HAPI 500");
    await action(w).trigger("click");
    expect(w.emitted("retry-fhir")?.[0]).toEqual([wf]);
  });
});

describe("ToolCard", () => {
  const mountTool = (tool: object) => mount(ToolCard, { props: { tool: tool as any }, global: { plugins } });

  it("approves a built tool from its button", async () => {
    const w = mountTool(GUI_TOOL);
    expect(sentence(w)).toBe("Built — not in the platform yet");
    await action(w).trigger("click");
    expect(w.emitted("submit-approve")?.[0]).toEqual(["t1"]);
  });

  it("launches a GUI tool in the platform; its backend failure is a chip and Launch retries", async () => {
    const tool = { ...GUI_TOOL, uuid: "a1", handoffStatus: "completed", deployStatus: "failed", deployError: "port in use",
      latestDeployId: "d1", version: "2" };
    const w = mountTool(tool);
    expect(sentence(w)).toBe("In the platform");
    expect(chips(w)).toEqual(["gui", "v2", "backend failed"]);
    await action(w).trigger("click");
    expect(w.emitted("launch")?.[0]).toEqual(["t1"]);
  });

  it("continues the registration of a tool that was never built", async () => {
    const tool = { ...GUI_TOOL, status: "pending", latestBuildId: undefined };
    const w = mountTool(tool);
    expect(sentence(w)).toBe("Not built yet");
    expect(action(w).text()).toBe("Continue registration");
    await action(w).trigger("click");
    expect(w.emitted("continue")?.[0]).toEqual([tool]);
  });

  it("adds or edits a tool's FHIR annotation until it is in the platform", () => {
    const w = mountTool(GUI_TOOL);
    expect(labels(w)).toContain("Add FHIR annotation");
    menu(w).find((m) => m.label === "Add FHIR annotation")!.onClick();
    expect(w.emitted("edit-annotation")?.[0]).toEqual([GUI_TOOL]);
    expect(labels(mountTool({ ...GUI_TOOL, hasAnnotation: true }))).toContain("Edit FHIR annotation");
    expect(labels(mountTool({ ...GUI_TOOL, uuid: "a1", handoffStatus: "completed" }))).not.toContain("Edit FHIR annotation");
    expect(labels(mountTool({ ...GUI_TOOL, uuid: "a1", handoffStatus: "completed", hasAnnotation: true })))
      .not.toContain("Edit FHIR annotation");
  });

  it("opens the logs of a running or failed build", async () => {
    const w = mountTool({ ...GUI_TOOL, status: "failed", buildError: "exit 1", latestBuildCreatedAt: "2026-11-06T10:00:00" });
    expect(w.find(".status__detail").text()).toBe("exit 1");
    await action(w).trigger("click");
    expect(w.emitted("view-logs")?.[0][0]).toMatchObject({ kind: "build", jobId: "b1", initialStatus: "failed" });
  });

  it("keeps the portal tool menu, renamed, and asks the hub to delete", () => {
    const w = mountTool(GUI_TOOL);
    expect(labels(w)).toEqual(["Launch", "Add FHIR annotation", "Rebuild", "View logs", "Delete tool"]);
    menu(w)[4].onClick();
    expect(w.emitted("delete")?.[0]).toEqual([GUI_TOOL]);
    expect(deleteTool).not.toHaveBeenCalled();

    const running = mountTool({ ...GUI_TOOL, uuid: "a1", handoffStatus: "completed", deployStatus: "completed", latestDeployId: "d1" });
    expect(labels(running)).toEqual(["Rebuild", "Stop backend", "View logs", "Delete tool"]);
    expect(labels(mountTool(TOOL))).toEqual(["Add FHIR annotation", "Rebuild", "View logs", "Delete tool"]);
  });

  it("offers only delete for a platform tool", () => {
    const w = mountTool(PLATFORM_TOOL);
    expect(sentence(w)).toBe("In the platform");
    expect(chips(w)).toEqual(["script"]);
    expect(labels(w)).toEqual(["Delete tool"]);
    menu(w)[0].onClick();
    expect(w.emitted("delete-platform")?.[0]).toEqual([PLATFORM_TOOL]);
  });

  it("names a gui workflow's tool's workflow, which owns rebuild, approval and delete", () => {
    const w = mountTool(WORKFLOW_TOOL);
    expect(chips(w)).toEqual(["gui", "from workflow_volview"]);
    expect(labels(w)).toEqual(["View logs"]);
    expect(action(w).text()).toBe("Launch");

    const backend = mountTool({ ...WORKFLOW_TOOL, hasBackend: true, deployStatus: "completed", latestDeployId: "d1" });
    expect(labels(backend)).toEqual(["Stop backend", "View logs"]);
    menu(backend)[0].onClick();
    expect(backend.emitted("compose-down")?.[0]).toEqual(["d1"]);
  });

  it("disables its button while the hub is busy", () => {
    const w = mount(ToolCard, { props: { tool: { ...GUI_TOOL, uuid: "a1", handoffStatus: "completed" } as any, disabled: true },
      global: { plugins } });
    expect(action(w).attributes("disabled")).toBeDefined();
  });
});

const measurement = (status: string, extra: object = {}) =>
  ({ id: "upload:m1", name: "m1", status, createdAt: "", updatedAt: "", ...extra });

describe("MeasurementCard", () => {
  const mountCard = (m: object) => mount(MeasurementCard, { props: { measurement: m as any }, global: { plugins } });

  it("approves a staged dataset with or without an annotation", async () => {
    for (const m of [measurement("pending"), measurement("pending", { hasAnnotation: true })]) {
      const w = mountCard(m);
      expect(sentence(w)).toBe("Ready to approve");
      await action(w).trigger("click");
      expect(w.emitted("approve")?.[0]).toEqual([m]);
    }
  });

  it("adds an annotation, or edits, previews and exports one", () => {
    expect(labels(mountCard(measurement("pending")))).toEqual(["Add FHIR annotation", "Delete measurement"]);
    expect(labels(mountCard(measurement("pending", { hasAnnotation: true }))))
      .toEqual(["Edit FHIR annotation", "Preview fhir.json", "Export annotation", "Delete measurement"]);
  });

  it("resumes a paused upload from its button; the menu cancels it", async () => {
    const w = mountCard(measurement("pending_upload"));
    expect(sentence(w)).toBe("Upload paused");
    await action(w).trigger("click");
    expect(w.emitted("resumeUpload")?.[0]).toEqual(["upload:m1"]);
    expect(labels(w)).toEqual(["Cancel upload"]);
  });

  it("retries a failed FHIR push from its button", async () => {
    const w = mountCard(measurement("fhir_failed", { uuid: "d1", failureMessage: "HAPI 500" }));
    expect(sentence(w)).toBe("In the platform — FHIR publishing failed");
    await action(w).trigger("click");
    expect(w.emitted("retryFhir")?.[0]).toEqual(["upload:m1"]);
  });

  it("asks the hub to delete, and stays as it is until the hub has deleted it", async () => {
    const w = mountCard(measurement("pending", { hasAnnotation: true }));
    menu(w).find((m) => m.label === "Delete measurement")!.onClick();
    await w.vm.$nextTick();
    expect(w.emitted("delete")).toHaveLength(1);
    expect(w.find(".ucard--disabled").exists()).toBe(false);
  });

  it("has no chips: its status line says it all", () => {
    expect(chips(mountCard(measurement("completed", { uuid: "d1", createdAt: "2026-10-01T10:00:00" })))).toEqual([]);
  });
});

describe("ModelCard", () => {
  const mountCard = (m: object) => mount(ModelCard, { props: { model: m as any }, global: { plugins } });

  it("uses the same sentences and actions as a measurement", async () => {
    const staged = mountCard(measurement("pending"));
    expect(sentence(staged)).toBe("Ready to approve");
    await action(staged).trigger("click");
    expect(staged.emitted("approve")).toHaveLength(1);
    expect(sentence(mountCard(measurement("uploading")))).toBe("Approving…");
    expect(sentence(mountCard(measurement("completed", { uuid: "d1" })))).toBe("In the platform");
  });

  it("adds or edits its FHIR annotation before and after approval", () => {
    expect(labels(mountCard(measurement("pending")))).toEqual(["Add FHIR annotation", "Cancel upload"]);
    expect(labels(mountCard(measurement("completed", { uuid: "d1", hasAnnotation: true }))))
      .toEqual(["Edit FHIR annotation", "Delete model"]);
    expect(labels(mountCard(measurement("completed", { uuid: "d1" })))).toEqual(["Add FHIR annotation", "Delete model"]);
  });

  it("shows a failure's reason under the sentence", () => {
    const w = mountCard(measurement("submit_failed", { failureMessage: "disk full" }));
    expect(sentence(w)).toBe("Approval failed");
    expect(w.find(".status__detail").text()).toBe("disk full");
    expect(action(w).text()).toBe("Approve again");
  });
});
