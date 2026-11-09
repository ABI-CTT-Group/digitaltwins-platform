import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { testVuetify } from "@/testing/vuetify";
import AssayPanel from "../components/AssayPanel.vue";
import { fixtureSource } from "../adapter/isaProjectSource";
import type { Catalogue, Study } from "../model/types";
import { emptySim, type Sim } from "../model/isaProject";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());

async function render(assayId: string, sim: Sim = emptySim(), tweak: (s: Study) => void = () => {}) {
  const catalogue: Catalogue = await fixtureSource.catalogue();
  const project = await fixtureSource.loadExample("example-breast-pilot");
  const study: Study = project.investigations[0].studies[0];
  tweak(study);
  wrapper = mount(AssayPanel, {
    props: { study, assayId, catalogue, sim },
    global: { plugins: [testVuetify()] },
  });
  return { w: wrapper, study };
}

const select = (w: VueWrapper, label: string) =>
  w.findAllComponents({ name: "VSelect" }).find(s => s.props("label") === label)!;

describe("AssayPanel", () => {
  it("lists the tools in the assay's workflow", async () => {
    const { w } = await render("a-pilot");
    const tools = w.findAll("[data-test=tool]").map(t => t.text());
    expect(tools).toEqual([
      expect.stringContaining("Segmentation inference (nnU-Net)"),
      expect.stringContaining("Surface mesher"),
      expect.stringContaining("Pilot report builder"),
    ]);
  });

  it("offers only workflows of the assay's type", async () => {
    const { w } = await render("a-analyse");
    expect(select(w, "Workflow").props("items").map((i: { id: string }) => i.id)).toEqual(["wf-cohort-select", "wf-analyse"]);
  });

  it("offers an upstream assay's planned dataset, marked as planned", async () => {
    const { w } = await render("a-pilot");
    const items = select(w, "seg_model").props("items");
    expect(items).toContainEqual(expect.objectContaining({
      key: "planned:a-train:seg_model", label: "Segmentation model", planned: true, producedBy: "Assay 4: train segmentation",
    }));
  });

  it("shows a picked planned dataset greyed, with the assay that will produce it", async () => {
    const { w, study } = await render("a-pilot");
    select(w, "seg_model").vm.$emit("update:modelValue", "planned:a-train:seg_model");
    await nextTick();
    expect(study.assays[4].inputs[1].source).toEqual({ kind: "planned", assayId: "a-train", port: "seg_model" });
    const chosen = w.find("[data-test=input-seg_model] .is-planned");
    expect(chosen.exists()).toBe(true);
    expect(chosen.text()).toContain("Will be produced by Assay 4: train segmentation");
  });

  it("stops greying a planned dataset once its producer's outputs are submitted", async () => {
    const ran = (await render("a-convert", { ran: ["a-cohort"], submitted: [] })).w;
    expect(ran.find("[data-test=input-cohort_list] .is-planned").exists()).toBe(true);
    const { w } = await render("a-convert", { ran: [], submitted: ["a-cohort"] });
    expect(w.find("[data-test=input-cohort_list] .is-planned").exists()).toBe(false);
    expect(w.find("[data-test=input-cohort_list]").text()).toContain("Produced by Assay 1: cohort selection");
  });

  it("warns when an input covers fewer subjects than the assay's cohort", async () => {
    const quiet = (await render("a-train")).w;
    expect(quiet.find("[data-test=input-labels] [data-test=cohort-warning]").exists()).toBe(false);
    const { w } = await render("a-train", emptySim(), s => { s.assays[3].cohort = []; });
    expect(w.find("[data-test=input-labels] [data-test=cohort-warning]").text())
      .toBe("Annotations will only cover subjects 1-10.");
  });

  it("names each output's planned dataset", async () => {
    const { w } = await render("a-pilot");
    expect(w.findAll("[data-test=output]").map(o => o.text())).toEqual([
      expect.stringContaining("meshes"), expect.stringContaining("report"),
    ]);
  });

  it("sets the cohort from a range list and rejects anything else", async () => {
    const { w, study } = await render("a-pilot");
    const field = w.findAllComponents({ name: "VTextField" }).find(f => f.props("label") === "Cohort (subjects)")!;
    field.vm.$emit("update:modelValue", "1-3,5");
    await nextTick();
    expect(study.assays[4].cohort).toEqual([1, 2, 3, 5]);
    field.vm.$emit("update:modelValue", "1-x");
    await nextTick();
    expect(study.assays[4].cohort).toEqual([1, 2, 3, 5]);
    expect(w.text()).toContain("Use subject numbers and ranges");
  });
});
