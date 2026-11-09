import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import type { Assay } from "../model/types";
import type { AssayStatus } from "../model/isaProject";

const assay: Assay = {
  id: "a-cohort", title: "Assay 1: cohort selection", type: "notebook", workflowId: "wf-cohort-select",
  cohort: [], inputs: [], outputs: [],
};

const render = (status: AssayStatus, selected = false, warnings: string[] = []) =>
  mount(SandboxAssayCard, { props: { assay, status, selected, warnings }, global: { plugins: [testVuetify()] } });

const button = (w: ReturnType<typeof render>, text: string) => w.findAll("button").find(b => b.text() === text)!;

describe("SandboxAssayCard", () => {
  it("shows the assay's title, type and status", () => {
    const w = render("blocked");
    expect(w.text()).toContain("Assay 1: cohort selection");
    expect(w.find(".card__tag").text()).toBe("notebook");
    expect(w.find("[data-test=status]").text()).toBe("Waiting on earlier assays");
    expect(render("ran").find("[data-test=status]").text()).toBe("Run, not submitted");
    expect(render("submitted").find("[data-test=status]").text()).toBe("Submitted (simulated)");
  });

  it("asks to be configured from the pencil and the expand icon", async () => {
    const w = render("ready");
    await w.find("[data-test=configure]").trigger("click");
    await w.find("[data-test=expand]").trigger("click");
    expect(w.emitted("configure")).toHaveLength(2);
  });

  it("launches when ready, run or submitted, never while blocked", async () => {
    const blocked = render("blocked");
    expect(button(blocked, "Launch").attributes("disabled")).toBeDefined();
    await button(blocked, "Launch").trigger("click");
    expect(blocked.emitted("launch")).toBeUndefined();

    for (const status of ["ready", "ran", "submitted"] as const) {
      const w = render(status);
      await button(w, "Launch").trigger("click");
      expect(w.emitted("launch")).toHaveLength(1);
    }
  });

  it("submits, and says which actions the prototype doesn't simulate", async () => {
    const w = render("ran");
    await button(w, "Submit").trigger("click");
    await button(w, "Download").trigger("click");
    expect(w.emitted("submit")).toHaveLength(1);
    expect(w.emitted("unavailable")).toEqual([["Download"]]);
  });

  it("flags a cohort warning", () => {
    expect(render("ready").find("[data-test=cohort-warning]").exists()).toBe(false);
    const w = render("ready", false, ["Annotations will only cover subjects 1-10."]);
    expect(w.find("[data-test=cohort-warning]").attributes("aria-label")).toBe("Annotations will only cover subjects 1-10.");
  });

  it("marks the selected card", () => {
    expect(render("ready", true).classes()).toContain("is-selected");
    expect(render("ready").classes()).not.toContain("is-selected");
  });
});
