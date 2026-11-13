import { afterEach, describe, expect, it } from "vitest";
import { mount, type VueWrapper } from "@vue/test-utils";
import StudyChain from "../components/StudyChain.vue";
import { fixtureSource } from "../adapter/isaProjectSource";
import type { Study } from "../model/types";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());

async function render(tweak: (s: Study) => void = () => {}) {
  const study = (await fixtureSource.loadExample("example-test-project")).investigations[0].studies[0];
  tweak(study);
  wrapper = mount(StudyChain, { props: { study } });
  return wrapper;
}

const columns = (w: VueWrapper) =>
  w.findAll("[data-test=chain-column]").map(c => c.findAll("[data-test=chain-chip]").map(x => x.text()));

describe("StudyChain", () => {
  it("draws the study's assays in run order, with the fork after image conversion as one column", async () => {
    const w = await render();
    expect(columns(w)).toEqual([
      ["Test Assay 1: cohort selection"],
      ["Test Assay 2: image conversion"],
      ["Test Assay 3: image visualisation", "Test Assay 4: breast app"],
    ]);
  });

  it("names the study and reads out the run order", async () => {
    const w = await render();
    expect(w.find(".chain__study").text()).toBe("Test Study");
    expect(w.find("[data-test=chain]").attributes("aria-label")).toBe(
      "Test Study runs Test Assay 1: cohort selection, then Test Assay 2: image conversion, " +
      "then Test Assay 3: image visualisation and Test Assay 4: breast app.");
  });

  it("tags each assay with its type", async () => {
    const w = await render();
    expect(w.findAll("[data-test=chain-chip]").map(c => c.attributes("data-type"))).toEqual(["notebook", "script", "gui", "gui"]);
  });

  it("says when a study has no assays yet", async () => {
    const w = await render(s => { s.assays = []; });
    expect(w.find("[data-test=chain-column]").exists()).toBe(false);
    expect(w.text()).toContain("No assays yet");
  });
});
