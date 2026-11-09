import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { testVuetify } from "@/testing/vuetify";
import StudyGraph from "../components/StudyGraph.vue";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import { fixtureSource } from "../adapter/isaProjectSource";
import { emptySim, type Sim } from "../model/isaProject";

type FlowNode = { id: string; type: string; data: unknown; position: { x: number; y: number } };
type FlowEdge = { id: string; label?: string; class: string };

// vue-flow needs real layout to draw, so the stub just renders each node through the page's slots.
const VueFlowStub = defineComponent({
  name: "VueFlow",
  props: ["nodes", "edges"],
  emits: ["node-click"],
  setup: (props, { slots }) => () =>
    h("div", (props.nodes as FlowNode[]).map(n => h("div", { key: n.id }, slots[`node-${n.type}`]?.({ id: n.id, data: n.data })))),
});

async function render(sim: Sim = emptySim(), selectedAssayId: string | null = null) {
  const catalogue = await fixtureSource.catalogue();
  const study = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies[0];
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
  it("lays the study out left to right, each producer before its consumers", async () => {
    const n = nodes(await render());
    const x = (id: string) => n.find(m => m.id === id)!.position.x;
    expect(x("existing:ds-clinical")).toBeLessThan(x("assay:a-cohort"));
    expect(x("assay:a-cohort")).toBeLessThan(x("assay:a-convert"));
    expect(x("assay:a-convert")).toBeLessThan(x("assay:a-annotate"));
    expect(x("assay:a-annotate")).toBeLessThan(x("assay:a-train"));
  });

  it("puts each platform dataset level with the assay it feeds", async () => {
    const n = nodes(await render());
    const y = (id: string) => n.find(m => m.id === id)!.position.y;
    expect(y("existing:ds-breast-mri") - y("assay:a-convert")).toBe(y("existing:ds-clinical") - y("assay:a-cohort"));
  });

  it("labels each edge with the datasets it carries, dashed until they exist", async () => {
    const before = await render();
    expect(edge(before, "assay:a-cohort->assay:a-convert")).toMatchObject({ label: "Cohort list" });
    expect(edge(before, "assay:a-cohort->assay:a-convert").class).toContain("edge-planned");
    expect(edge(before, "existing:ds-breast-mri->assay:a-convert").class).not.toContain("edge-planned");

    expect(edge(await render({ ran: ["a-cohort"], submitted: [] }), "assay:a-cohort->assay:a-convert").class).toContain("edge-planned");
    const after = await render({ ran: [], submitted: ["a-cohort"] });
    expect(edge(after, "assay:a-cohort->assay:a-convert").class).not.toContain("edge-planned");
  });

  it("draws each assay as a card, and passes its actions on", async () => {
    const w = await render(emptySim(), "a-train");
    const cards = w.findAllComponents(SandboxAssayCard);
    expect(cards).toHaveLength(6);
    expect(cards.every(c => Array.isArray(c.props("warnings")))).toBe(true);
    expect(cards.filter(c => c.props("selected")).map(c => c.props("assay").id)).toEqual(["a-train"]);

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
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "assay:a-train") });
    flow.vm.$emit("node-click", { node: nodes(w).find(n => n.id === "existing:ds-clinical") });
    expect(w.emitted("configure")).toEqual([["a-train"]]);
  });
});
