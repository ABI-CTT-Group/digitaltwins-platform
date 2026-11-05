import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import { testVuetify } from "@/testing/vuetify";

const tools = vi.hoisted(() => ({
  useCreateTool: vi.fn(), useGetTool: vi.fn(), useCreateToolAnnotation: vi.fn(), useGetWorkflowToolAnnotation: vi.fn(),
  useWorkflowToolBuild: vi.fn(),
}));
const workflows = vi.hoisted(() => ({
  useCreateWorkflow: vi.fn(), useGetWorkflow: vi.fn(), useCreateWorkflowAnnotation: vi.fn(), useGetWorkflowAnnotation: vi.fn(),
  useWorkflowBuild: vi.fn(),
}));
const logConsole = vi.hoisted(() => ({ openConsole: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => tools);
vi.mock("@/bootstrap/workflow_api", () => workflows);
vi.mock("@/composables/useLogConsole", () => ({ useLogConsole: () => logConsole }));

import RegisterWizard from "../RegisterWizard.vue";

// The steps have their own specs; here each is a button that calls what the wizard hands it.
const dirty = ref(false);
const stepAuth = ref<object | undefined>(undefined);
const stubs = {
  BaseInformationStep: defineComponent({
    props: ["type", "submit"],
    setup(props, { expose }) {
      expose({ dirty });
      return () => h("button", { class: "info-save", onClick: () => props.submit({ name: "curator" }, stepAuth.value) }, "save");
    },
  }),
  BaseAnnotateStep: defineComponent({
    props: ["type", "data", "pendingAuth", "savedNote", "submit"],
    emits: ["skip", "close"],
    setup(props, { emit }) {
      return () => h("div", { class: "annotate", "data-auth": JSON.stringify(props.pendingAuth ?? null), "data-saved": props.savedNote ?? "" }, [
        h("button", { class: "annotate-save", onClick: () => props.submit(props.data.id, '{"inputs":[]}') }, "save"),
        h("button", { class: "annotate-skip", onClick: () => emit("skip") }, "skip"),
      ]);
    },
  }),
  BaseBuildStep: defineComponent({
    props: ["type", "data", "submit"],
    setup(props) { return () => h("button", { class: "build-start", onClick: () => props.submit(props.data.id) }, "build"); },
  }),
  RebuildAuthDialog: defineComponent({
    props: ["modelValue", "sourceType", "busy", "title"],
    emits: ["submit", "cancel", "update:modelValue"],
    setup(props, { emit }) {
      return () => props.modelValue
        ? h("button", { class: "auth-submit", onClick: () => emit("submit", { token: "t0k" }) }, "token") : null;
    },
  }),
};

const TOOL = { id: "t1", name: "curator", label: "GUI", version: "1.0", sourceType: "local", repositoryUrl: "" };

async function setup(path: string, type: "tool" | "workflow" = "tool") {
  const base = type === "tool" ? "/catalogue/tools" : "/catalogue/workflows";
  const names = type === "tool"
    ? ["UploadToolDataset", "RegisterTool", "ContinueToolRegistration"]
    : ["UploadWorkflowDataset", "RegisterWorkflow", "ContinueWorkflowRegistration"];
  const router = createRouter({ history: createMemoryHistory(), routes: [{
    path: base, component: RouterView, children: [
      { path: "", name: names[0], component: { render: () => h("p", { class: "hub" }, "hub") } },
      { path: "new", name: names[1], component: RegisterWizard, props: { type } },
      { path: ":id/register", name: names[2], component: RegisterWizard, props: (r) => ({ type, id: r.params.id }) },
    ],
  }] });
  await router.push(path);
  const w = mount(RouterView, { global: { plugins: [router, testVuetify()], stubs } });
  await flushPromises();
  return { router, w };
}
const click = async (w: ReturnType<typeof mount>, selector: string) => { await w.find(selector).trigger("click"); await flushPromises(); };

describe("RegisterWizard", () => {
  beforeEach(() => {
    tools.useCreateTool.mockResolvedValue(TOOL);
    tools.useGetTool.mockResolvedValue(TOOL);
    tools.useGetWorkflowToolAnnotation.mockRejectedValue({ response: { status: 404 } });
    tools.useWorkflowToolBuild.mockResolvedValue({ buildId: "b1" });
    workflows.useGetWorkflow.mockResolvedValue({ ...TOOL, id: "w1", name: "seg" });
    workflows.useGetWorkflowAnnotation.mockRejectedValue({ response: { status: 404 } });
    workflows.useWorkflowBuild.mockResolvedValue({ buildId: "b2" });
  });
  afterEach(() => { vi.resetAllMocks(); dirty.value = false; stepAuth.value = undefined; });

  it("creates the tool once, then continues at its own URL with step 1 read-only", async () => {
    const { router, w } = await setup("/catalogue/tools/new");
    await click(w, ".info-save");

    expect(tools.useCreateTool).toHaveBeenCalledOnce();
    expect(router.currentRoute.value.fullPath).toBe("/catalogue/tools/t1/register?step=annotation");
    expect(w.find(".info-save").exists()).toBe(false);
    expect(w.find(".annotate").exists()).toBe(true);
    expect(w.text()).toContain("curator");
  });

  it("opens an existing tool at the step its URL names, without creating it again", async () => {
    const { w } = await setup("/catalogue/tools/t1/register?step=build");
    expect(tools.useGetTool).toHaveBeenCalledWith("t1");
    expect(w.find(".build-start").exists()).toBe(true);
    expect(w.find(".info-save").exists()).toBe(false);
    expect(tools.useCreateTool).not.toHaveBeenCalled();
  });

  it("skips the annotation without saving one", async () => {
    const { router, w } = await setup("/catalogue/tools/t1/register?step=annotation");
    await click(w, ".annotate-skip");
    expect(tools.useCreateToolAnnotation).not.toHaveBeenCalled();
    expect(router.currentRoute.value.query.step).toBe("build");
  });

  it("saves the annotation, then moves to the build", async () => {
    const { router, w } = await setup("/catalogue/tools/t1/register?step=annotation");
    await click(w, ".annotate-save");
    expect(tools.useCreateToolAnnotation).toHaveBeenCalledWith("t1", { fhirNote: '{"inputs":[]}', sparcNote: "" });
    expect(router.currentRoute.value.query.step).toBe("build");
  });

  it("hands the saved annotation to the step to edit", async () => {
    tools.useGetWorkflowToolAnnotation.mockResolvedValue({ fhirNote: '{"name":"tool_curator"}' });
    const { w } = await setup("/catalogue/tools/t1/register?step=annotation");
    expect(w.find(".annotate").attributes("data-saved")).toBe('{"name":"tool_curator"}');
  });

  it("starts the build with step 1's token, opens its logs, and returns to the hub", async () => {
    stepAuth.value = { token: "from-step-1" };
    tools.useCreateTool.mockResolvedValue({ ...TOOL, sourceType: "github" });
    tools.useGetTool.mockResolvedValue({ ...TOOL, sourceType: "github" });
    const { router, w } = await setup("/catalogue/tools/new");
    await click(w, ".info-save");
    expect(w.find(".auth-submit").exists()).toBe(false);
    expect(w.find(".annotate").attributes("data-auth")).toBe('{"token":"from-step-1"}');
    await click(w, ".annotate-skip");
    await click(w, ".build-start");

    expect(tools.useWorkflowToolBuild).toHaveBeenCalledWith("t1", { token: "from-step-1" });
    expect(logConsole.openConsole).toHaveBeenCalledWith("build", "b1", "curator", "building");
    expect(router.currentRoute.value.name).toBe("UploadToolDataset");
  });

  it("asks for a git source's token again when you continue a registration later", async () => {
    tools.useGetTool.mockResolvedValue({ ...TOOL, id: "t2", sourceType: "gitlab" });
    const { w } = await setup("/catalogue/tools/t2/register?step=annotation");
    expect(w.find(".annotate").exists()).toBe(false);
    await click(w, ".auth-submit");
    expect(w.find(".annotate").attributes("data-auth")).toBe('{"token":"t0k"}');
  });

  it("warns before leaving step 1 with unsaved input", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { router } = await setup("/catalogue/tools/new");
    dirty.value = true;
    await router.push("/catalogue/tools");
    expect(confirm).toHaveBeenCalledOnce();
    expect(router.currentRoute.value.name).toBe("RegisterTool");
    confirm.mockRestore();
  });

  it("registers a workflow the same way", async () => {
    workflows.useCreateWorkflow.mockResolvedValue({ ...TOOL, id: "w1", name: "seg" });
    const { router, w } = await setup("/catalogue/workflows/new", "workflow");
    await click(w, ".info-save");
    expect(router.currentRoute.value.fullPath).toBe("/catalogue/workflows/w1/register?step=annotation");
    await click(w, ".annotate-save");
    expect(workflows.useCreateWorkflowAnnotation).toHaveBeenCalledWith("w1", { fhirNote: '{"inputs":[]}', sparcNote: "" });
    await click(w, ".build-start");
    expect(workflows.useWorkflowBuild).toHaveBeenCalledWith("w1", undefined);
    expect(router.currentRoute.value.name).toBe("UploadWorkflowDataset");
  });
});
