import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import SandboxAssayCard from "../components/SandboxAssayCard.vue";
import type { Assay } from "../model/types";
import type { AssayStatus } from "../model/isaProject";
import type { PlatformLink } from "../platformRun";

const assay: Assay = {
  id: "a-cohort", title: "Assay 1: cohort selection", type: "notebook", workflowId: "wf-cohort-select",
  cohort: [], inputs: [], outputs: [],
};

const render = (status: AssayStatus, selected = false, warnings: string[] = [], platform?: PlatformLink, a: Assay = assay) =>
  mount(SandboxAssayCard, { props: { assay: a, status, selected, warnings, platform }, global: { plugins: [testVuetify()] } });

const link = (extra: Partial<PlatformLink> = {}): PlatformLink =>
  ({ seekId: "41", canMonitor: false, launching: false, downloading: false, submitting: false, ...extra });

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

  it("passes Submit, Verify and Download on, for its study to run or explain", async () => {
    const w = render("ran");
    await button(w, "Submit").trigger("click");
    await button(w, "Verify").trigger("click");
    await button(w, "Download").trigger("click");
    expect(w.emitted("submit")).toHaveLength(1);
    expect(w.emitted("verify")).toHaveLength(1);
    expect(w.emitted("download")).toHaveLength(1);
  });

  it("links to the platform assay it runs, and drops \"simulated\" once submitted", () => {
    expect(render("ready").find("[data-test=platform-assay]").exists()).toBe(false);
    const w = render("submitted", false, [], link());
    const a = w.find("[data-test=platform-assay]");
    expect(a.text()).toBe("Platform assay 41");
    expect(a.attributes("href")).toBe("/launched-assay?assayId=41");
    expect(a.attributes("target")).toBe("_blank");
    expect(w.find("[data-test=status]").text()).toBe("Submitted");
  });

  it("monitors a launched platform script, and shows requests in flight", async () => {
    const script: Assay = { ...assay, type: "script" };
    expect(button(render("ran", false, [], link(), script), "Monitor").attributes("disabled")).toBeDefined();
    const w = render("ran", false, [], link({ canMonitor: true }), script);
    await button(w, "Monitor").trigger("click");
    expect(w.emitted("monitor")).toHaveLength(1);

    const busy = render("ran", false, [], link({ launching: true, downloading: true, submitting: true }));
    expect(button(busy, "Launch").attributes("disabled")).toBeDefined();
    expect(busy.text()).toContain("Downloading...");
    expect(busy.text()).toContain("Submitting...");
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
