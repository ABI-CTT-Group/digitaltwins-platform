import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { testVuetify } from "@/testing/vuetify";
import StudyGraph from "../components/StudyGraph.vue";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import { fixtureSource } from "../adapter/isaProjectSource";
import { emptySim, type Sim } from "../model/isaProject";

type FlowNode = { id: string; type: string; data: unknown; position: { x: number; y: number } };
type FlowEdge = { id: string; type: string; data: { labels: string[] }; class: string };

// vue-flow needs real layout to draw, so the stub just renders each node through the page's slots.
const VueFlowStub = defineComponent({
  name: "VueFlow",
  props: ["nodes", "edges"],
  emits: ["node-click"],
  setup: (props, { slots }) => () =>
    h("div", (props.nodes as FlowNode[]).map(n => h("div", { key: n.id }, slots[`node-${n.type}`]?.({ id: n.id, data: n.data })))),
});

async function render(sim: Sim = emptySim(), selectedAssayId: string | null = null, bundledDataset?: string) {
  const catalogue = await fixtureSource.catalogue();
  const bundled = catalogue.datasets.find(d => d.id === bundledDataset);
  if (bundled) bundled.bundled = { fileCount: 1, bytes: 1 };
  const study = (await fixtureSource.loadExample("example-test-project")).investigations[0].studies[0];
  return mount(StudyGraph, {
    props: { study, catalogue, sim, selectedAssayId },
    global: { plugins: [testVuetify()], stubs: { VueFlow: VueFlowStub, Handle: true } },
  });
}

type W = Awaited<ReturnType<typeof render>>;
const nodes = (w: W) => w.findComponent({ name: "VueFlow" }).props("nodes") as FlowNode[];
const edges = (w: W) => w.findComponent({ name: "VueFlow" }).props("edges") as FlowEdge[];
const edge = (w: W, id: string) => edges(w).find(e => e.id === id)!;

describe("StudyGraph", () => {
  it("tags a source dataset that came in the project's bundle as bundled", async () => {
    const w = await render(emptySim(), null, "ds-test-dicom");
    const tags = w.findAll(".node-source__bundled");
    expect(tags).toHaveLength(1);
    expect(tags[0].element.parentElement!.textContent).toContain("test_dicom");
  });

  it("lays the study out left to right, each producer before its consumers, with the fork in one column", async () => {
    const n = nodes(await render());
    const x = (id: string) => n.find(m => m.id === id)!.position.x;
    expect(x("existing:ds-test-dicom")).toBeLessThan(x("assay:a-cohort"));
    expect(x("assay:a-cohort")).toBeLessThan(x("assay:a-convert"));
    expect(x("assay:a-convert")).toBeLessThan(x("assay:a-visualise"));
    expect(x("assay:a-visualise")).toBe(x("assay:a-breast-app"));
  });

  it("keeps a platform dataset read by the first assay level with it", async () => {
    const n = nodes(await render());
    const y = (id: string) => n.find(m => m.id === id)!.position.y;
    expect(y("existing:ds-test-dicom")).toBeGreaterThan(y("assay:a-cohort"));
    expect(y("existing:ds-test-dicom")).toBeLessThan(y("assay:a-cohort") + 150);
  });

  it("puts the breast app's platform datasets just before it, below the assay in that column", async () => {
    const n = nodes(await render());
    const at = (id: string) => n.find(m => m.id === id)!.position;
    for (const id of ["existing:ds-test-data-breast-app", "existing:ds-test-model-breast-app"]) {
      expect(at(id).x).toBe(at("assay:a-convert").x);
      expect(at(id).y).toBeGreaterThan(at("assay:a-convert").y + 200); // clear of the card
    }
    expect(at("existing:ds-test-model-breast-app").y).toBeGreaterThan(at("existing:ds-test-data-breast-app").y);
    expect(at("assay:a-convert").y).toBe(at("assay:a-cohort").y); // the datasets don't push the assay off centre
  });

  it("labels each edge with the datasets it carries, dashed until they exist", async () => {
    const before = await render();
    const labels = (id: string) => edge(before, id).data.labels;
    expect(edges(before).every(e => e.type === "dataset")).toBe(true);
    expect(labels("assay:a-cohort->assay:a-convert")).toEqual(["test_curated_dataset / curated_dataset"]);
    expect(labels("assay:a-convert->assay:a-visualise")).toEqual(["test_converted / nifti_output"]);
    expect(labels("assay:a-convert->assay:a-breast-app")).toEqual(["test_converted / nrrd_output"]);
    expect(labels("existing:ds-test-data-breast-app->assay:a-breast-app")).toEqual(["14 inputs"]);
    expect(labels("existing:ds-test-model-breast-app->assay:a-breast-app")).toEqual([]);
    expect(edge(before, "assay:a-cohort->assay:a-convert").class).toContain("edge-planned");
    expect(edge(before, "existing:ds-test-dicom->assay:a-cohort").class).not.toContain("edge-planned");

    expect(edge(await render({ ran: ["a-cohort"], submitted: [] }), "assay:a-cohort->assay:a-convert").class).toContain("edge-planned");
    const after = await render({ ran: [], submitted: ["a-cohort"] });
    expect(edge(after, "assay:a-cohort->assay:a-convert").class).not.toContain("edge-planned");
  });

  it("draws each assay as a card, and passes its actions on", async () => {
    const w = await render(emptySim(), "a-breast-app");
    const cards = w.findAllComponents(SandboxAssayCard);
    expect(cards).toHaveLength(4);
    expect(cards.every(c => Array.isArray(c.props("warnings")))).toBe(true);
    expect(cards.filter(c => c.props("selected")).map(c => c.props("assay").id)).toEqual(["a-breast-app"]);

    cards[0].vm.$emit("configure");
    cards[0].vm.$emit("launch");
    cards[0].vm.$emit("submit");
    cards[0].vm.$emit("unavailable", "Verify");
    expect(w.emitted("configure")).toEqual([["a-cohort"]]);
    expect(w.emitted("launch")).toEqual([["a-cohort"]]);
    expect(w.emitted("submit")).toEqual([["a-cohort"]]);
    expect(w.emitted("unavailable")).toEqual([["Verify"]]);
  });

  it("opens an assay when its card is clicked", async () => {
    const w = await render();
    const flow = w.findComponent({ name: "VueFlow" });
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "assay:a-breast-app") });
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "existing:ds-test-dicom") });
    expect(w.emitted("configure")).toEqual([["a-breast-app"]]);
  });
});
