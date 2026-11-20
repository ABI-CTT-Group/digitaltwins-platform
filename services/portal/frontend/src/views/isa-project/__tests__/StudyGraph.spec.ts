import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { testVuetify } from "@/testing/vuetify";
import StudyGraph from "../components/StudyGraph.vue";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import { fixtureSource } from "../adapter/isaProjectSource";
import { emptySim, type Sim } from "../model/isaProject";
import type { PlatformLink } from "../platformRun";

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

async function render(sim: Sim = emptySim(), selectedAssayId: string | null = null, bundledDataset?: string, platform?: Record<string, PlatformLink>, direction: "TB" | "LR" = "LR") {
  const catalogue = await fixtureSource.catalogue();
  const bundled = catalogue.datasets.find(d => d.id === bundledDataset);
  if (bundled) bundled.bundled = { fileCount: 1, bytes: 1 };
  const study = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies[1];
  return mount(StudyGraph, {
    props: { study, catalogue, sim, selectedAssayId, platform, direction },
    global: { plugins: [testVuetify()], stubs: { VueFlow: VueFlowStub, Handle: true } },
  });
}

type W = Awaited<ReturnType<typeof render>>;
const nodes = (w: W) => w.findComponent({ name: "VueFlow" }).props("nodes") as FlowNode[];
const edges = (w: W) => w.findComponent({ name: "VueFlow" }).props("edges") as FlowEdge[];
const edge = (w: W, id: string) => edges(w).find(e => e.id === id)!;

describe("StudyGraph", () => {
  it("tags a source dataset that came in the project's bundle as bundled", async () => {
    const w = await render(emptySim(), null, "ds-dicom");
    const tags = w.findAll(".node-source__bundled");
    expect(tags).toHaveLength(1);
    expect(tags[0].element.parentElement!.textContent).toContain("dicom");
  });

  it("lays the study out left to right, each producer before its consumers, with the fork in one column", async () => {
    const n = nodes(await render());
    const x = (id: string) => n.find(m => m.id === id)!.position.x;
    expect(x("existing:ds-dicom")).toBeLessThan(x("assay:a-pipeline-cohort"));
    expect(x("assay:a-pipeline-cohort")).toBeLessThan(x("assay:a-pipeline-convert"));
    expect(x("assay:a-pipeline-convert")).toBeLessThan(x("assay:a-pipeline-visualise"));
    expect(x("assay:a-pipeline-visualise")).toBe(x("assay:a-pipeline-breast-app"));
  });

  it("keeps a platform dataset read by the first assay level with it", async () => {
    const n = nodes(await render());
    const y = (id: string) => n.find(m => m.id === id)!.position.y;
    expect(y("existing:ds-dicom")).toBeGreaterThan(y("assay:a-pipeline-cohort"));
    expect(y("existing:ds-dicom")).toBeLessThan(y("assay:a-pipeline-cohort") + 150);
  });

  it("puts the breast app's platform datasets just before it, below the assay in that column", async () => {
    const n = nodes(await render());
    const at = (id: string) => n.find(m => m.id === id)!.position;
    for (const id of ["existing:ds-data-breast-app", "existing:ds-model-breast-app"]) {
      expect(at(id).x).toBe(at("assay:a-pipeline-convert").x);
      expect(at(id).y).toBeGreaterThan(at("assay:a-pipeline-convert").y + 200); // clear of the card
    }
    expect(at("existing:ds-model-breast-app").y).toBeGreaterThan(at("existing:ds-data-breast-app").y);
    expect(at("assay:a-pipeline-convert").y).toBe(at("assay:a-pipeline-cohort").y); // the datasets don't push the assay off centre
  });

  it("lays the study out top to bottom, each producer above its consumers, with the fork in one row", async () => {
    const n = nodes(await render(emptySim(), null, undefined, undefined, "TB"));
    const y = (id: string) => n.find(m => m.id === id)!.position.y;
    expect(y("existing:ds-dicom")).toBeLessThan(y("assay:a-pipeline-cohort"));
    expect(y("assay:a-pipeline-cohort")).toBeLessThan(y("assay:a-pipeline-convert"));
    expect(y("assay:a-pipeline-convert")).toBeLessThan(y("assay:a-pipeline-visualise"));
    expect(y("assay:a-pipeline-visualise")).toBe(y("assay:a-pipeline-breast-app"));
  });

  it("top to bottom, puts a platform dataset just above the assay that reads it", async () => {
    const n = nodes(await render(emptySim(), null, undefined, undefined, "TB"));
    const at = (id: string) => n.find(m => m.id === id)!.position;
    expect(at("existing:ds-dicom").y).toBeLessThan(at("assay:a-pipeline-cohort").y);
    expect(at("existing:ds-dicom").y).toBeGreaterThan(at("assay:a-pipeline-cohort").y - 150);
    expect(at("existing:ds-dicom").x).toBeGreaterThan(at("assay:a-pipeline-cohort").x);
    expect(at("existing:ds-dicom").x).toBeLessThan(at("assay:a-pipeline-cohort").x + 330);
  });

  it("top to bottom, puts the breast app's platform datasets side by side above it, clear of its incoming label", async () => {
    const n = nodes(await render(emptySim(), null, undefined, undefined, "TB"));
    const at = (id: string) => n.find(m => m.id === id)!.position;
    const app = at("assay:a-pipeline-breast-app");
    for (const id of ["existing:ds-data-breast-app", "existing:ds-model-breast-app"]) {
      expect(at(id).y).toBeLessThan(app.y);
      expect(at(id).y).toBeGreaterThan(at("assay:a-pipeline-convert").y + 200); // clear of the convert card
      expect(at(id).x).toBeGreaterThan(app.x + 165); // right of the card's centre, where the edge label sits
    }
    expect(at("existing:ds-model-breast-app").x).toBeGreaterThan(at("existing:ds-data-breast-app").x + 200);
    expect(at("assay:a-pipeline-convert").x).toBe(at("assay:a-pipeline-cohort").x); // the datasets don't push the assay off centre
  });

  it("labels each edge with the datasets it carries, dashed until they exist", async () => {
    const before = await render();
    const labels = (id: string) => edge(before, id).data.labels;
    expect(edges(before).every(e => e.type === "dataset")).toBe(true);
    expect(labels("assay:a-pipeline-cohort->assay:a-pipeline-convert")).toEqual(["curated_dataset / curated_dataset"]);
    expect(labels("assay:a-pipeline-convert->assay:a-pipeline-visualise")).toEqual(["converted / nifti_output"]);
    expect(labels("assay:a-pipeline-convert->assay:a-pipeline-breast-app")).toEqual(["converted / nrrd_output"]);
    expect(labels("existing:ds-data-breast-app->assay:a-pipeline-breast-app")).toEqual(["14 inputs"]);
    expect(labels("existing:ds-model-breast-app->assay:a-pipeline-breast-app")).toEqual([]);
    expect(edge(before, "assay:a-pipeline-cohort->assay:a-pipeline-convert").class).toContain("edge-planned");
    expect(edge(before, "existing:ds-dicom->assay:a-pipeline-cohort").class).not.toContain("edge-planned");

    expect(edge(await render({ ran: ["a-pipeline-cohort"], submitted: [] }), "assay:a-pipeline-cohort->assay:a-pipeline-convert").class).toContain("edge-planned");
    const after = await render({ ran: [], submitted: ["a-pipeline-cohort"] });
    expect(edge(after, "assay:a-pipeline-cohort->assay:a-pipeline-convert").class).not.toContain("edge-planned");
  });

  it("draws each assay as a card, and passes its actions on", async () => {
    const w = await render(emptySim(), "a-pipeline-breast-app");
    const cards = w.findAllComponents(SandboxAssayCard);
    expect(cards).toHaveLength(4);
    expect(cards.every(c => Array.isArray(c.props("warnings")))).toBe(true);
    expect(cards.filter(c => c.props("selected")).map(c => c.props("assay").id)).toEqual(["a-pipeline-breast-app"]);

    cards[0].vm.$emit("configure");
    cards[0].vm.$emit("launch");
    cards[0].vm.$emit("submit");
    cards[0].vm.$emit("monitor");
    cards[0].vm.$emit("verify");
    cards[0].vm.$emit("download");
    expect(w.emitted("configure")).toEqual([["a-pipeline-cohort"]]);
    expect(w.emitted("launch")).toEqual([["a-pipeline-cohort"]]);
    expect(w.emitted("submit")).toEqual([["a-pipeline-cohort"]]);
    expect(w.emitted("monitor")).toEqual([["a-pipeline-cohort"]]);
    expect(w.emitted("verify")).toEqual([["a-pipeline-cohort"]]);
    expect(w.emitted("download")).toEqual([["a-pipeline-cohort"]]);
  });

  it("hands each card the platform assay it is linked to", async () => {
    const a1: PlatformLink = { seekId: "41", canMonitor: false, launching: false, downloading: false, submitting: false };
    const w = await render(emptySim(), null, undefined, { "a-pipeline-cohort": a1 });
    expect(w.findAllComponents(SandboxAssayCard).map(c => c.props("platform"))).toEqual([a1, undefined, undefined, undefined]);
  });

  it("opens an assay when its card is clicked", async () => {
    const w = await render();
    const flow = w.findComponent({ name: "VueFlow" });
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "assay:a-pipeline-breast-app") });
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "existing:ds-dicom") });
    expect(w.emitted("configure")).toEqual([["a-pipeline-breast-app"]]);
  });
});
