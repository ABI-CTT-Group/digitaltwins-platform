import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";
import { fixtureSource } from "../adapter/isaProjectSource";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

import IsaProjectHub from "../IsaProjectHub.vue";
import StudyChain from "../components/StudyChain.vue";
import BundleUploadDialog from "../components/BundleUploadDialog.vue";
import IsaApproveDialog from "../components/IsaApproveDialog.vue";
import { useIsaProjectStore } from "../isaProjectStore";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => { push.mockClear(); setActivePinia(createPinia()); });

async function render() {
  wrapper = mount(IsaProjectHub, { attachTo: document.body, global: { plugins: [testVuetify()], stubs: { BackLink: true } } });
  await flushPromises();
  return wrapper;
}

const rows = (w: VueWrapper) => w.findAll("[data-test=isa-row]");
const row = (w: VueWrapper, title: string) => rows(w).find(r => r.find(".row__title").text() === title)!;

/** Opens a row's More actions menu (Vuetify renders it into the body) and finds an item in it. */
async function menuItem(w: VueWrapper, title: string, item: string) {
  const r = row(w, title);
  await r.find("[data-test=more]").trigger("click");
  await flushPromises();
  const id = r.attributes("data-project");
  return document.body.querySelector<HTMLButtonElement>(`[data-test="menu-${id}"] [data-test=${item}]`);
}

async function uploadFile(w: VueWrapper, text: string) {
  const input = w.find("input[type=file]");
  // jsdom's File has no text(); browsers do.
  const file = Object.assign(new File([text], "p.json"), { text: async () => text });
  Object.defineProperty(input.element, "files", { value: [file], configurable: true });
  await input.trigger("change");
  await flushPromises();
}

const mine = async () => {
  const p = await fixtureSource.loadExample("example-breast-pilot");
  return JSON.stringify({ ...p, project: { id: "p-mine", title: "My study plan" } });
};

describe("IsaProjectHub", () => {
  it("lists the example ISA projects with what they hold", async () => {
    const w = await render();
    expect(rows(w)).toHaveLength(1);
    expect(row(w, "Breast").text()).toContain("Example");
    expect(row(w, "Breast").text()).toContain("1 investigation, 2 studies, 14 assays");
  });

  it("previews each study's chain of assays", async () => {
    const w = await render();
    const chains = w.findAllComponents(StudyChain);
    expect(chains.map(c => c.props("study").title)).toEqual(["Te Whatu Ora Breast Pilot", "Image pipeline test"]);
    expect(row(w, "Breast").find("[data-test=chain]").exists()).toBe(true);
  });

  it("shows each project's investigations and their studies", async () => {
    const w = await render();
    const investigations = row(w, "Breast").findAll("[data-test=isa-investigation]");
    expect(investigations.map(i => i.find("[data-test=isa-investigation-open]").text())).toEqual([
      expect.stringContaining("Breast Radiology Report"),
    ]);
    const studies = investigations[0].findAll("[data-test=isa-study]");
    expect(studies.map(s => s.find("[data-test=isa-study-open]").text())).toEqual([
      expect.stringMatching(/Te Whatu Ora Breast Pilot.*10 assays/),
      expect.stringMatching(/Image pipeline test.*4 assays/),
    ]);
    expect(studies.every(s => s.findComponent(StudyChain).exists())).toBe(true);
  });

  it("opens an investigation in the study dashboard", async () => {
    const w = await render();
    await row(w, "Breast").find("[data-test=isa-investigation-open]").trigger("click");
    expect(push).toHaveBeenCalledWith({ name: "StudyDashboardPrototype", query: { trail: [
      "te-whatu-ora-radiology-reporting",
      "te-whatu-ora-radiology-reporting:p-breast",
      "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report",
    ].join(",") } });
  });

  it("opens a study in the study dashboard", async () => {
    const w = await render();
    await row(w, "Breast").findAll("[data-test=isa-study-open]")[1].trigger("click");
    expect(push).toHaveBeenCalledWith({ name: "StudyDashboardPrototype", query: { trail: [
      "te-whatu-ora-radiology-reporting",
      "te-whatu-ora-radiology-reporting:p-breast",
      "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report",
      "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-image-pipeline-test",
    ].join(",") } });
  });

  it("says when an investigation has no studies", async () => {
    const w = await render();
    const p = JSON.parse(await mine());
    p.investigations[0].studies = [];
    await uploadFile(w, JSON.stringify(p));
    expect(row(w, "My study plan").find("[data-test=isa-investigation]").text()).toContain("No studies yet");
  });

  it("keeps the downloads and Reset in a menu", async () => {
    const w = await render();
    expect(row(w, "Breast").text()).not.toMatch(/Download JSON|Download bundle|Reset/);
    for (const item of ["download-json", "download-bundle", "reset"]) {
      expect(await menuItem(w, "Breast", item), item).not.toBeNull();
    }
    expect(await menuItem(w, "Breast", "remove")).toBeNull();
  });

  it("never says prototype", async () => {
    const w = await render();
    expect(w.text()).not.toMatch(/prototype|kept in this browser/i);
    expect(w.text()).toContain("open it in the study dashboard");
  });

  it("opens a project in the study dashboard (prototype)", async () => {
    const w = await render();
    await row(w, "Breast").find("[data-test=open]").trigger("click");
    expect(push).toHaveBeenCalledWith({ name: "StudyDashboardPrototype", query: { trail: "te-whatu-ora-radiology-reporting,te-whatu-ora-radiology-reporting:p-breast" } });
  });

  it("adds an uploaded project to the list", async () => {
    const w = await render();
    await uploadFile(w, await mine());
    expect(row(w, "My study plan").text()).toContain("Uploaded");
  });

  it("says why an upload can't be loaded", async () => {
    const w = await render();
    await uploadFile(w, '{"schemaVersion":"0.1-draft"}');
    expect(w.find("[data-test=upload-errors]").text()).toContain("project needs an id and a title");
    expect(rows(w)).toHaveLength(1);
  });

  it("asks before replacing a project that has the same id", async () => {
    const w = await render();
    await uploadFile(w, await mine());
    await uploadFile(w, await mine());
    const dialog = w.findComponent({ name: "ConfirmDialog" });
    expect(dialog.props("title")).toBe("Replace My study plan?");
  });

  it("offers Remove for uploads and Reset for examples, each after asking", async () => {
    const w = await render();
    await uploadFile(w, await mine());
    expect(await menuItem(w, "Breast", "remove")).toBeNull();
    expect(await menuItem(w, "Breast", "reset")).not.toBeNull();

    (await menuItem(w, "My study plan", "remove"))!.click();
    await flushPromises();
    const dialog = w.findComponent({ name: "ConfirmDialog" });
    expect(dialog.props("title")).toBe("Remove My study plan?");
    await (dialog.props("action") as () => Promise<unknown>)();
    await flushPromises();
    expect(rows(w)).toHaveLength(1);
  });

  it("offers a second upload, with datasets, for designs whose data isn't on the platform yet", async () => {
    const w = await render();
    expect(w.findComponent(BundleUploadDialog).props("modelValue")).toBe(false);
    await w.find("[data-test=upload-bundle]").trigger("click");
    expect(w.findComponent(BundleUploadDialog).props("modelValue")).toBe(true);
  });

  it("lists a bundled project with the new items it brought, asking before it replaces one", async () => {
    const w = await render();
    const project = JSON.parse(await mine());
    const bundledFiles = { fileCount: 1, bytes: 1 };
    const bundled = {
      datasets: [{ id: "ds-a", name: "ds-a", category: "measurements", bundled: bundledFiles },
        { id: "ds-b", name: "ds-b", category: "measurements", bundled: bundledFiles }],
      workflows: [],
      tools: [{ id: "t-a", name: "tool_a", type: "script", bundled: bundledFiles }],
    };
    w.findComponent(BundleUploadDialog).vm.$emit("add", { project, bundled });
    await flushPromises();
    expect(row(w, "My study plan").text()).toContain("with 2 bundled datasets, 1 bundled tool");

    w.findComponent(BundleUploadDialog).vm.$emit("add", { project, bundled });
    await flushPromises();
    expect(w.findComponent({ name: "ConfirmDialog" }).props("title")).toBe("Replace My study plan?");
  });

  it("offers Approve for uploads, not for examples, saying what it will do", async () => {
    const w = await render();
    await uploadFile(w, await mine());
    expect(row(w, "Breast").find("[data-test=approve]").exists()).toBe(false);
    expect(row(w, "My study plan").find("[data-test=approval]").text())
      .toBe("Not in the platform yet. Approve it to create its SEEK project.");
    await row(w, "My study plan").find("[data-test=approve]").trigger("click");
    const dialog = w.findComponent(IsaApproveDialog);
    expect([dialog.props("modelValue"), dialog.props("projectId")]).toEqual([true, "p-mine"]);
  });

  it("counts the bundled items an approval will register", async () => {
    const w = await render();
    const bundled = { fileCount: 1, bytes: 1 };
    useIsaProjectStore().addBundle(JSON.parse(await mine()), {
      datasets: [{ id: "ds-a", name: "ds-a", category: "measurements", bundled }],
      workflows: [], tools: [{ id: "t-a", name: "tool_a", type: "script", bundled }],
    });
    await flushPromises();
    expect(row(w, "My study plan").find("[data-test=approval]").text())
      .toBe("Not in the platform yet. Approve it to create its SEEK project and register its 2 bundled items.");
  });

  it("follows an approval on the row, then says the project is in the platform", async () => {
    const w = await render();
    await uploadFile(w, await mine());
    const entry = useIsaProjectStore().entries.find(e => e.project.project.id === "p-mine")!;
    entry.approval = { state: "approving", stage: "Creating the SEEK project" };
    await flushPromises();
    expect(row(w, "My study plan").find("[data-test=approval]").text()).toBe("Approving… Creating the SEEK project");
    expect(row(w, "My study plan").find("[data-test=approve]").exists()).toBe(false);
    entry.approval = { state: "approved" };
    await flushPromises();
    expect(row(w, "My study plan").find("[data-test=approval]").text()).toBe("In the platform");

    (await menuItem(w, "My study plan", "remove"))!.click();
    await flushPromises();
    expect(w.findComponent({ name: "ConfirmDialog" }).props("text")).toContain("Its registered datasets, workflows and tools stay");
  });

  it("downloads any project as a bundle: its JSON plus a skeleton of the datasets it uses", async () => {
    const created: Blob[] = [];
    const create = vi.spyOn(URL, "createObjectURL").mockImplementation(b => { created.push(b as Blob); return "blob:x"; });
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {}); // jsdom can't navigate
    const w = await render();
    (await menuItem(w, "Breast", "download-bundle"))!.click();
    await vi.waitFor(() => expect(created).toHaveLength(1));
    const { default: JSZip } = await import("jszip");
    const zip = await JSZip.loadAsync(created[0]);
    expect(zip.file("p-breast/isa-project.json")).not.toBeNull();
    expect(zip.file("p-breast/datasets/ds-dicom/dataset_description.xlsx")).not.toBeNull();
    create.mockRestore();
    revoke.mockRestore();
    click.mockRestore();
  });
});
