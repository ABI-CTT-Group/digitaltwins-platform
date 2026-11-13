import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, h } from "vue";
import { testVuetify } from "@/testing/vuetify";
import StudyDesign from "../StudyDesign.vue";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";

// vue-flow needs real layout; StudyGraph's own spec covers what it hands vue-flow.
const VueFlowStub = defineComponent({ name: "VueFlow", props: ["nodes", "edges"], setup: () => () => h("div") });
const RouterLinkStub = defineComponent({ name: "RouterLink", props: ["to"], setup: (_, { slots }) => () => h("a", slots.default?.()) });

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
});

async function render(studyId = "s-test") {
  wrapper = mount(StudyDesign, {
    props: { projectId: "p-test-project", studyId },
    global: { plugins: [testVuetify()], stubs: { VueFlow: VueFlowStub, RouterLink: RouterLinkStub } },
  });
  await flushPromises();
  return wrapper;
}

const graph = (w: VueWrapper) => w.findComponent({ name: "StudyGraph" });
const panel = (w: VueWrapper) => w.findComponent({ name: "AssayPanel" });

describe("StudyDesign", () => {
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
    const w = await render();
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
    const w = await render();
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
    const w = await render();
    graph(w).vm.$emit("unavailable", "Verify");
    await flushPromises();
    expect(w.text()).toContain("Verify isn't part of the prototype");
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
