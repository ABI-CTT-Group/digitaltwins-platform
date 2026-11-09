import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";
import { fixtureSource } from "../adapter/isaProjectSource";

const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

import IsaProjectHub from "../IsaProjectHub.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => { push.mockClear(); setActivePinia(createPinia()); });

async function render() {
  wrapper = mount(IsaProjectHub, { global: { plugins: [testVuetify()], stubs: { BackLink: true } } });
  await flushPromises();
  return wrapper;
}

const rows = (w: VueWrapper) => w.findAll("[data-test=isa-row]");
const row = (w: VueWrapper, title: string) => rows(w).find(r => r.text().includes(title))!;

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
    expect(row(w, "Breast pilot (example)").text()).toContain("Example");
    expect(row(w, "Breast pilot (example)").text()).toContain("1 investigation, 1 study, 6 assays");
  });

  it("opens a project in the study dashboard", async () => {
    const w = await render();
    await row(w, "Breast pilot").find("[data-test=open]").trigger("click");
    expect(push).toHaveBeenCalledWith({ name: "StudyDashboard", query: { trail: "isa-sandbox,isa-sandbox:p-breast-pilot" } });
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
    expect(row(w, "Breast pilot").find("[data-test=remove]").exists()).toBe(false);
    expect(row(w, "Breast pilot").find("[data-test=reset]").exists()).toBe(true);

    await row(w, "My study plan").find("[data-test=remove]").trigger("click");
    const dialog = w.findComponent({ name: "ConfirmDialog" });
    expect(dialog.props("title")).toBe("Remove My study plan?");
    await (dialog.props("action") as () => Promise<unknown>)();
    await flushPromises();
    expect(rows(w)).toHaveLength(1);
  });
});
