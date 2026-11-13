import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h, ref } from "vue";
import { testVuetify } from "@/testing/vuetify";

const run = vi.hoisted(() => ({ launchPlatformAssay: vi.fn(), submitPlatformAssay: vi.fn() }));
vi.mock("../platformRun", async importOriginal => ({ ...(await importOriginal<object>()), ...run }));
const actions = vi.hoisted(() => ({ monitor: vi.fn(), verify: vi.fn(), download: vi.fn() }));
vi.mock("@/composables/useAssayActions", () => ({
  useAssayActions: () => ({ ...actions, downloadingMap: ref({}) }),
}));

import StudyDesign from "../StudyDesign.vue";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import { useIsaProjectStore } from "../isaProjectStore";
import { fixtureSource } from "../adapter/isaProjectSource";
import { useDashboardCacheStore } from "@/store/dashboard_cache_store";

// vue-flow needs real layout; StudyGraph's own spec covers what it hands vue-flow.
const VueFlowStub = defineComponent({ name: "VueFlow", props: ["nodes", "edges"], setup: () => () => h("div") });
const RouterLinkStub = defineComponent({ name: "RouterLink", props: ["to"], setup: (_, { slots }) => () => h("a", slots.default?.()) });

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  setActivePinia(createPinia());
});

/** The Test Project, uploaded under another id: not linked to the platform, so it only simulates. */
async function addUpload() {
  const project = await fixtureSource.loadExample("example-test-project");
  project.project.id = "p-upload";
  const store = useIsaProjectStore();
  await store.ensureExamples();
  store.entries.push({ project, source: "upload" });
}

async function render(studyId = "s-test", projectId = "p-test-project") {
  wrapper = mount(StudyDesign, {
    props: { projectId, studyId },
    global: { plugins: [testVuetify()], stubs: { VueFlow: VueFlowStub, RouterLink: RouterLinkStub } },
  });
  await flushPromises();
  return wrapper;
}

const graph = (w: VueWrapper) => w.findComponent({ name: "StudyGraph" });
const panel = (w: VueWrapper) => w.findComponent({ name: "AssayPanel" });

describe("StudyDesign", () => {
  it("lets assays use items an approval registered, as platform items", async () => {
    const { useIsaProjectStore } = await import("../isaProjectStore");
    useIsaProjectStore().registered.datasets.push({ id: "ds-reg", name: "ds-reg", category: "measurements" });
    const w = await render();
    const ds = graph(w).props("catalogue").datasets.find((d: { id: string }) => d.id === "ds-reg");
    expect(ds).toEqual({ id: "ds-reg", name: "ds-reg", category: "measurements" });
  });

  it("adds the datasets that came with a bundled project to what its assays can use", async () => {
    const { useIsaProjectStore } = await import("../isaProjectStore");
    const store = useIsaProjectStore();
    await store.ensureExamples();
    const bundled = { datasets: [{ id: "ds-new", name: "ds-new", category: "measurements" as const, bundled: { fileCount: 1, bytes: 1 } }], workflows: [], tools: [] };
    store.entries[0].bundled = bundled;
    const w = await render();
    expect(graph(w).props("catalogue").datasets.map((d: { id: string }) => d.id)).toContain("ds-new");
  });

  it("shows the Flow view first, and remembers a switch to List", async () => {
    const w = await render();
    expect(graph(w).props("study").id).toBe("s-test");
    await w.find("[data-test=view-list]").trigger("click");
    expect(graph(w).exists()).toBe(false);
    expect(w.find("[data-test=assay-list]").exists()).toBe(true);

    w.unmount();
    expect((await render()).find("[data-test=assay-list]").exists()).toBe(true);
  });

  it("lists every assay as a card, in the study's order", async () => {
    const w = await render();
    await w.find("[data-test=view-list]").trigger("click");
    expect(w.findAllComponents(SandboxAssayCard).map(c => c.props("assay").id))
      .toEqual(["a-cohort", "a-convert", "a-visualise", "a-breast-app"]);
  });

  it("opens an assay's configuration in the side panel", async () => {
    const w = await render();
    expect(panel(w).exists()).toBe(false);
    graph(w).vm.$emit("configure", "a-breast-app");
    await flushPromises();
    expect(panel(w).props("assayId")).toBe("a-breast-app");
    expect(graph(w).props("selectedAssayId")).toBe("a-breast-app");
  });

  it("runs an assay from its card, and makes its outputs available only once submitted", async () => {
    await addUpload();
    const w = await render("s-test", "p-upload");
    graph(w).vm.$emit("launch", "a-cohort");
    await flushPromises();
    expect(graph(w).props("sim")).toEqual({ ran: ["a-cohort"], submitted: [] });
    expect(w.text()).toContain("Ran Test Assay 1: cohort selection. Submit its outputs so later assays can use them.");

    graph(w).vm.$emit("submit", "a-cohort");
    await flushPromises();
    expect(graph(w).props("sim")).toEqual({ ran: [], submitted: ["a-cohort"] });
    expect(w.text()).toContain("Submitted Test Assay 1: cohort selection");

    await w.find("[data-test=simulate]").trigger("click");
    expect(graph(w).props("sim")).toEqual({ ran: [], submitted: ["a-cohort", "a-convert"] });
    expect(w.text()).toContain("Ran and submitted Test Assay 2: image conversion");
  });

  it("explains a Submit or Launch that has nothing to do", async () => {
    await addUpload();
    const w = await render("s-test", "p-upload");
    graph(w).vm.$emit("submit", "a-cohort");
    await flushPromises();
    expect(w.text()).toContain("Test Assay 1: cohort selection has no run to submit. Launch it first.");

    graph(w).vm.$emit("launch", "a-cohort");
    graph(w).vm.$emit("launch", "a-cohort");
    await flushPromises();
    expect(w.text()).toContain("Test Assay 1: cohort selection has already run (simulated). Submit its outputs next.");

    graph(w).vm.$emit("submit", "a-cohort");
    graph(w).vm.$emit("launch", "a-cohort");
    await flushPromises();
    expect(w.text()).toContain("Test Assay 1: cohort selection is already submitted (simulated). Reset to start again.");
    graph(w).vm.$emit("submit", "a-cohort");
    await flushPromises();
    expect(w.text()).toContain("Test Assay 1: cohort selection is already submitted (simulated).");
    expect(graph(w).props("sim")).toEqual({ ran: [], submitted: ["a-cohort"] });
  });

  it("says when an action isn't part of the prototype", async () => {
    await addUpload();
    const w = await render("s-test", "p-upload");
    expect(w.text()).toContain("nothing runs");
    graph(w).vm.$emit("verify", "a-cohort");
    await flushPromises();
    expect(w.text()).toContain("Verify isn't part of the prototype");
    expect(actions.verify).not.toHaveBeenCalled();
    expect(run.launchPlatformAssay).not.toHaveBeenCalled();
    expect(graph(w).props("platform")).toEqual({});
  });

  describe("the Test Project example, linked to the platform's Test Project", () => {
    it("says its actions run the platform assays", async () => {
      const w = await render();
      expect(w.text()).toContain("Launch, Submit and Download run the linked platform assays");
      expect(Object.fromEntries(Object.entries(graph(w).props("platform")).map(([k, v]) => [k, (v as { seekId: string }).seekId])))
        .toEqual({ "a-cohort": "41", "a-convert": "42", "a-visualise": "43", "a-breast-app": "45" });
    });

    it("launches the platform assay, and counts it as run only once it started", async () => {
      const w = await render();
      run.launchPlatformAssay.mockResolvedValueOnce(false);
      graph(w).vm.$emit("launch", "a-cohort");
      await flushPromises();
      expect(run.launchPlatformAssay).toHaveBeenCalledWith("41");
      expect(graph(w).props("sim")).toEqual({ ran: [], submitted: [] });

      run.launchPlatformAssay.mockResolvedValueOnce(true);
      graph(w).vm.$emit("launch", "a-cohort");
      await flushPromises();
      expect(graph(w).props("sim")).toEqual({ ran: ["a-cohort"], submitted: [] });
      expect(w.text()).toContain("Launched Test Assay 1: cohort selection on the platform.");

      // An assay can run many times.
      run.launchPlatformAssay.mockResolvedValueOnce(true);
      graph(w).vm.$emit("launch", "a-cohort");
      await flushPromises();
      expect(run.launchPlatformAssay).toHaveBeenCalledTimes(3);
      expect(graph(w).props("sim")).toEqual({ ran: ["a-cohort"], submitted: [] });
    });

    it("doesn't launch an assay still waiting on earlier ones", async () => {
      const w = await render();
      graph(w).vm.$emit("launch", "a-convert");
      await flushPromises();
      expect(run.launchPlatformAssay).not.toHaveBeenCalled();
    });

    it("submits the platform run, and counts it as submitted only once it worked", async () => {
      const w = await render();
      run.launchPlatformAssay.mockResolvedValue(true);
      graph(w).vm.$emit("launch", "a-cohort");
      await flushPromises();

      run.submitPlatformAssay.mockResolvedValueOnce(false);
      graph(w).vm.$emit("submit", "a-cohort");
      await flushPromises();
      expect(run.submitPlatformAssay).toHaveBeenCalledWith("41");
      expect(graph(w).props("sim")).toEqual({ ran: ["a-cohort"], submitted: [] });

      run.submitPlatformAssay.mockResolvedValueOnce(true);
      graph(w).vm.$emit("submit", "a-cohort");
      await flushPromises();
      expect(graph(w).props("sim")).toEqual({ ran: [], submitted: ["a-cohort"] });
      expect(w.text()).toContain("Submitted Test Assay 1: cohort selection");
    });

    it("monitors, verifies and downloads the platform assay", async () => {
      const w = await render();
      expect(graph(w).props("platform")["a-convert"].canMonitor).toBe(false);
      useDashboardCacheStore().setAssayExecute("42", "Monitor", "http://airflow/dags/workflow_116");
      await flushPromises();
      expect(graph(w).props("platform")["a-convert"].canMonitor).toBe(true);

      graph(w).vm.$emit("monitor", "a-convert");
      graph(w).vm.$emit("verify", "a-cohort");
      graph(w).vm.$emit("download", "a-cohort");
      expect(actions.monitor).toHaveBeenCalledWith("42");
      expect(actions.verify).toHaveBeenCalledWith("41");
      expect(actions.download).toHaveBeenCalledWith("41");
    });
  });

  it("has no study-level upload: ISA projects are uploaded from the catalogue", async () => {
    const w = await render();
    expect(w.text()).not.toContain("Load study design");
    expect(w.findAllComponents(RouterLinkStub)).toHaveLength(0);
  });

  it("says so when the study isn't in this browser", async () => {
    const w = await render("nope");
    expect(w.text()).toContain("This study isn't in the ISA projects stored in this browser");
  });
});
