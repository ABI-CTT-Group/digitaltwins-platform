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

async function render(assayId: string, sim: Sim = emptySim(), tweak: (s: Study) => void = () => {},
  tweakCatalogue: (c: Catalogue) => void = () => {}) {
  const catalogue: Catalogue = await fixtureSource.catalogue();
  tweakCatalogue(catalogue);
  const project = await fixtureSource.loadExample("example-breast-pilot");
  const study: Study = project.investigations[0].studies[1];
  tweak(study);
  wrapper = mount(AssayPanel, {
    props: { study, assayId, catalogue, sim },
    global: { plugins: [testVuetify()] },
  });
  return { w: wrapper, study };
}

const select = (w: VueWrapper, label: string) =>
  w.findAllComponents({ name: "VSelect" }).find(s => s.props("label") === label)!;

const group = (w: VueWrapper, title: string) =>
  w.findAll("[data-test=input-group]").find(g => g.find(".group__title").text() === title)!;

describe("AssayPanel", () => {
  it("lists the tools in the assay's workflow", async () => {
    const { w } = await render("a-pipeline-convert");
    expect(w.findAll("[data-test=tool]").map(t => t.text())).toEqual([
      expect.stringContaining("tool_dicom_to_nifti"),
      expect.stringContaining("tool_dicom_to_nrrd"),
    ]);
  });

  it("offers only workflows of the assay's type", async () => {
    const { w } = await render("a-pipeline-visualise");
    expect(select(w, "Workflow").props("items").map((i: { id: string }) => i.id)).toEqual(["wf-volview", "wf-lesion-curator"]);
  });

  it("offers a platform dataset and the planned dataset of the same name side by side", async () => {
    const { w } = await render("a-pipeline-convert");
    expect(select(w, "dicom_input").props("items").map((i: { label: string; planned: boolean }) => [i.label, i.planned]))
      .toContainEqual(["curated_dataset", false]);
    expect(select(w, "dicom_input").props("items")).toContainEqual(expect.objectContaining({
      key: "planned:a-pipeline-cohort:curated_dataset", label: "curated_dataset / curated_dataset", planned: true,
      producedBy: "1. Cohort selection",
    }));
  });

  it("shows a picked planned dataset greyed, with the assay that will produce it", async () => {
    const { w, study } = await render("a-pipeline-visualise", emptySim(), s => { s.assays[2].inputs[0].source = null; });
    select(w, "dicom_file").vm.$emit("update:modelValue", "planned:a-pipeline-convert:nifti_output");
    await nextTick();
    expect(study.assays[2].inputs[0].source).toEqual({ kind: "planned", assayId: "a-pipeline-convert", port: "nifti_output" });
    const chosen = w.find("[data-test=input-dicom_file] .is-planned");
    expect(chosen.exists()).toBe(true);
    expect(chosen.text()).toContain("converted / nifti_output");
    expect(chosen.text()).toContain("Will be produced by 2. Image conversion");
  });

  it("stops greying a planned dataset once its producer's outputs are submitted", async () => {
    const ran = (await render("a-pipeline-convert", { ran: ["a-pipeline-cohort"], submitted: [] })).w;
    expect(ran.find("[data-test=input-dicom_input] .is-planned").exists()).toBe(true);
    const { w } = await render("a-pipeline-convert", { ran: [], submitted: ["a-pipeline-cohort"] });
    expect(w.find("[data-test=input-dicom_input] .is-planned").exists()).toBe(false);
    expect(w.find("[data-test=input-dicom_input]").text()).toContain("Produced by 1. Cohort selection");
  });

  it("warns when an input covers fewer subjects than the assay's cohort", async () => {
    const quiet = (await render("a-pipeline-convert")).w;
    expect(quiet.find("[data-test=input-dicom_input] [data-test=cohort-warning]").exists()).toBe(false);
    const { w } = await render("a-pipeline-convert", emptySim(), s => { s.assays[0].cohort = [2]; });
    expect(w.find("[data-test=input-dicom_input] [data-test=cohort-warning]").text())
      .toBe("curated_dataset will only cover subjects 2.");
  });

  it("groups the inputs by the dataset they read, with how many read each", async () => {
    const { w } = await render("a-pipeline-breast-app");
    expect(w.findAll("[data-test=input-group]").map(g => [g.find(".group__title").text(), g.find(".group__count").text()]))
      .toEqual([["converted", "1"], ["data_breast_app", "14"], ["model_breast_app", "1"]]);
    expect(group(w, "converted").text()).toContain("Will be produced by 2. Image conversion");
    expect(group(w, "data_breast_app").text()).toContain("On the platform");
  });

  it("says when a dataset came with the project's upload rather than from the platform", async () => {
    const { w } = await render("a-pipeline-breast-app", emptySim(), () => {}, c => {
      c.datasets.find(d => d.id === "ds-data-breast-app")!.bundled = { fileCount: 1, bytes: 1 };
    });
    expect(group(w, "data_breast_app").text()).toContain("Bundled with this project, not on the platform yet");
    expect(group(w, "model_breast_app").text()).toContain("On the platform");
  });

  it("starts a group of four or more inputs collapsed, and opens it on request", async () => {
    const { w } = await render("a-pipeline-breast-app");
    const toggle = () => group(w, "data_breast_app").find("[data-test=group-toggle]");
    expect(toggle().attributes("aria-expanded")).toBe("false");
    expect(w.find("[data-test=input-t2_nrrd]").exists()).toBe(false);
    expect(w.find("[data-test=input-contrast_pre_nrrd]").exists()).toBe(true);
    await toggle().trigger("click");
    expect(toggle().attributes("aria-expanded")).toBe("true");
    expect(w.find("[data-test=input-t2_nrrd]").exists()).toBe(true);
  });

  it("lists inputs with no source under 'Not chosen yet', always open", async () => {
    const { w } = await render("a-pipeline-breast-app", emptySim(), s => { s.assays[3].inputs.forEach(i => (i.source = null)); });
    const none = group(w, "Not chosen yet");
    expect(none.find(".group__count").text()).toBe("16");
    expect(none.find("[data-test=group-toggle]").exists()).toBe(false);
    expect(w.find("[data-test=input-t2_nrrd]").exists()).toBe(true);
  });

  it("names each output dataset once, with the outputs that fill it", async () => {
    const { w } = await render("a-pipeline-convert");
    const groups = w.findAll("[data-test=output-group]");
    expect(groups).toHaveLength(1);
    expect(groups[0].text()).toContain("nifti_output");
    expect(groups[0].text()).toContain("nrrd_output");
  });

  it("renames every output that fills a dataset when its name is changed", async () => {
    const { w, study } = await render("a-pipeline-breast-app");
    const field = w.findAllComponents({ name: "VTextField" }).find(f => f.props("label") === "Dataset name")!;
    const input = field.find("input");
    await input.setValue("lesion_curation");
    await input.trigger("change");
    expect(new Set(study.assays[3].outputs.map(o => o.datasetName))).toEqual(new Set(["lesion_curation"]));
    expect(study.assays[3].outputs).toHaveLength(12);
  });

  it("sets the cohort from a range list and rejects anything else", async () => {
    const { w, study } = await render("a-pipeline-breast-app");
    const field = w.findAllComponents({ name: "VTextField" }).find(f => f.props("label") === "Cohort (subjects)")!;
    field.vm.$emit("update:modelValue", "1-3,5");
    await nextTick();
    expect(study.assays[3].cohort).toEqual([1, 2, 3, 5]);
    field.vm.$emit("update:modelValue", "1-x");
    await nextTick();
    expect(study.assays[3].cohort).toEqual([1, 2, 3, 5]);
    expect(w.text()).toContain("Use subject numbers and ranges");
  });
});
