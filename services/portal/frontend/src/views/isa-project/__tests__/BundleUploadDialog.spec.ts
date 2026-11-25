import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent } from "vue";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import { fixtureSource } from "../adapter/isaProjectSource";
import BundleUploadDialog from "../components/BundleUploadDialog.vue";

// The real dropzone scans folders with browser APIs jsdom lacks; the stub only emits what it would.
const Dropzone = defineComponent({ name: "LocalFolderDropzone", emits: ["source-selected"], template: "<div />" });

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); });

async function render() {
  wrapper = mount(BundleUploadDialog, {
    props: { modelValue: true },
    attachTo: document.body,
    global: { plugins: [testVuetify()], stubs: { LocalFolderDropzone: Dropzone } },
  });
  await flushPromises();
  return wrapper;
}

const file = (path: string, text: string) =>
  Object.assign(new File([text], path.split("/").pop()!), { webkitRelativePath: path, text: async () => text });

/** The example project, with its first assay reading a new dataset that the bundle brings. */
async function bundle(datasetFolder = "ds-new-scans") {
  const p = await fixtureSource.loadExample("example-breast-pilot");
  p.project = { id: "p-bundled", title: "Bundled plan" };
  p.investigations[0].studies[0].assays[0].inputs[0].source = { kind: "existing", datasetId: "ds-new-scans" };
  const files = [
    file("plan/isa-project.json", JSON.stringify(p)),
    file(`plan/datasets/${datasetFolder}/dataset_description.xlsx`, ""),
    file(`plan/datasets/${datasetFolder}/primary/sub-1/a.dcm`, "abcd"),
  ];
  return { kind: "folder" as const, files, rootName: "plan", fileCount: files.length, totalSize: 0 };
}

const body = () => document.body.querySelector("[data-test=bundle-dialog]")!;
const programme = () => body().querySelector<HTMLSelectElement>("[data-test=bundle-programme]")!;
const programmeName = () => body().querySelector<HTMLInputElement>("[data-test=bundle-programme-name]");
const BUILT_IN = { id: "te-whatu-ora-radiology-reporting", name: "Te Whatu Ora Radiology Reporting" };

/** Picks a single JSON file through the dialog's own file input. */
async function pickJson(text: string) {
  const input = body().querySelector<HTMLInputElement>("[data-test=bundle-json]")!;
  const f = Object.assign(new File([text], "plan.json"), { text: async () => text });
  Object.defineProperty(input, "files", { value: [f], configurable: true });
  input.dispatchEvent(new Event("change"));
  await flushPromises();
}

async function choose(el: HTMLSelectElement | HTMLInputElement, value: string) {
  el.value = value;
  el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? "change" : "input"));
  await flushPromises();
}
const addButton = () => body().querySelector<HTMLButtonElement>("[data-test=bundle-add]")!;

async function drop(w: VueWrapper, source: Awaited<ReturnType<typeof bundle>>) {
  w.findComponent(Dropzone).vm.$emit("source-selected", source);
  await flushPromises();
}

describe("BundleUploadDialog", () => {
  it("is the one way to upload a study design", async () => {
    await render();
    expect(body().querySelector("#bundle-title")!.textContent).toBe("Upload study design");
    expect(body().textContent).toContain("Pick the study design JSON on its own");
    expect(body().textContent).toContain("the Breast project with one bundled dataset");
    expect(body().textContent).not.toMatch(/ISA project/i);
    expect(body().querySelector("[data-test=bundle-json]")!.getAttribute("accept")).toContain(".json");
  });

  it("reviews a lone JSON, with nothing bundled", async () => {
    await render();
    const p = await fixtureSource.loadExample("example-breast-pilot");
    await pickJson(JSON.stringify({ ...p, project: { id: "p-json", title: "JSON plan" } }));
    expect(body().querySelector("[data-test=bundle-review]")!.textContent).toContain("JSON plan");
    expect(body().querySelectorAll("[data-test=bundle-item]")).toHaveLength(0);
    expect(body().textContent).not.toContain("Bundled items");
    expect(body().querySelector("[data-test=bundle-on-platform]")!.textContent).toContain("4 datasets, 8 workflows");
    expect(addButton().disabled).toBe(false);
  });

  it("shows how to lay out a bundle before one is chosen", async () => {
    await render();
    expect(body().textContent).toContain("datasets/<id>/");
    expect(body().querySelector("[data-test=bundle-review]")).toBeNull();
  });

  it("offers an example bundle to try", async () => {
    await render();
    const link = body().querySelector("[data-test=bundle-example]");
    expect(link?.textContent).toContain("Download an example bundle");
  });

  it("lists what the bundle adds, and what is already on the platform", async () => {
    const w = await render();
    await drop(w, await bundle());
    const rows = Array.from(body().querySelectorAll("[data-test=bundle-item]"), r => r.textContent);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toContain("ds-new-scans");
    expect(rows[0]).toContain("measurements, 2 files, 4 B");
    expect(rows[0]).toContain("1. Cohort selection");
    expect(body().querySelector("[data-test=bundle-on-platform]")!.textContent).toContain("4 datasets, 8 workflows");
    expect(addButton().disabled).toBe(false);
  });

  it("says what is wrong and won't add the project", async () => {
    const w = await render();
    await drop(w, await bundle("ds-other"));
    expect(body().querySelector("[data-test=bundle-errors]")!.textContent)
      .toContain("unknown dataset ds-new-scans (no datasets/ds-new-scans/ folder in the bundle)");
    expect(body().querySelector("[data-test=bundle-warnings]")!.textContent).toContain("datasets/ds-other/ isn't used");
    expect(addButton().disabled).toBe(true);
  });

  it("hands the project, its new items and its programme over, and closes", async () => {
    const w = await render();
    await drop(w, await bundle());
    expect(addButton().textContent!.trim()).toBe("Add project");
    expect(body().textContent).toContain("The study dashboard lists the project under it.");
    addButton().click();
    await flushPromises();
    const [[added]] = w.emitted("add") as [[{ project: { project: { id: string } }; bundled: { datasets: { id: string }[] }; programme: unknown }]];
    expect(added.project.project.id).toBe("p-bundled");
    expect(added.bundled.datasets.map(d => d.id)).toEqual(["ds-new-scans"]);
    expect(added.programme).toEqual(BUILT_IN);
    expect(w.emitted("update:modelValue")).toEqual([[false]]);
  });

  it("offers the programmes projects are in, the built-in one first, or a new one", async () => {
    const { useIsaProjectStore } = await import("../isaProjectStore");
    const p = await fixtureSource.loadExample("example-breast-pilot");
    useIsaProjectStore().entries.push({ project: p, source: "upload", programme: { id: "isa-cardiac", name: "Cardiac" } });
    const w = await render();
    await drop(w, await bundle());
    expect(Array.from(programme().options, o => o.textContent!.trim()))
      .toEqual(["Te Whatu Ora Radiology Reporting", "Cardiac", "New programme…"]);
    expect(programme().value).toBe(BUILT_IN.id);
    expect(programmeName()).toBeNull();

    await choose(programme(), "isa-cardiac");
    addButton().click();
    await flushPromises();
    expect((w.emitted("add") as [[{ programme: unknown }]])[0][0].programme).toEqual({ id: "isa-cardiac", name: "Cardiac" });
  });

  it("files the project in a new programme once it has a name", async () => {
    const w = await render();
    await drop(w, await bundle());
    await choose(programme(), "new");
    expect(addButton().disabled).toBe(true);
    await choose(programmeName()!, "   ");
    expect(addButton().disabled).toBe(true);
    await choose(programmeName()!, "Radiology research");
    expect(addButton().disabled).toBe(false);
    addButton().click();
    await flushPromises();
    expect((w.emitted("add") as [[{ programme: unknown }]])[0][0].programme)
      .toEqual({ id: "isa-radiology-research", name: "Radiology research" });
  });

  it("counts an item an approval registered as on the platform", async () => {
    const { useIsaProjectStore } = await import("../isaProjectStore");
    useIsaProjectStore().registered.datasets.push({ id: "ds-new-scans", name: "ds-new-scans", category: "measurements" });
    const w = await render();
    await drop(w, await bundle("ds-unused"));
    expect(addButton().disabled).toBe(false);
    expect(body().querySelector("[data-test=bundle-on-platform]")!.textContent).toContain("5 datasets");
  });

  it("goes back to choosing a bundle", async () => {
    const w = await render();
    await drop(w, await bundle());
    body().querySelector<HTMLButtonElement>("[data-test=bundle-again]")!.click();
    await flushPromises();
    expect(body().querySelector("[data-test=bundle-review]")).toBeNull();
  });
});
