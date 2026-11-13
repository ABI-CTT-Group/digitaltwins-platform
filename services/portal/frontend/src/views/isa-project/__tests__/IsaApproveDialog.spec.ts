import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";
import { fixtureSource } from "../adapter/isaProjectSource";
import { APPROVE_STEP, useIsaProjectStore } from "../isaProjectStore";
import IsaApproveDialog from "../components/IsaApproveDialog.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => { wrapper?.unmount(); vi.useRealTimers(); });
beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); });

async function render() {
  const store = useIsaProjectStore();
  const p = await fixtureSource.loadExample("example-test-project");
  store.addBundle({ ...p, project: { id: "p-mine", title: "My study plan" } }, {
    datasets: [{ id: "ds-new", name: "ds-new", category: "measurements", bundled: { fileCount: 1, bytes: 1 } }],
    workflows: [], tools: [],
  });
  wrapper = mount(IsaApproveDialog, {
    props: { modelValue: true, projectId: "p-mine" },
    attachTo: document.body,
    global: { plugins: [testVuetify()] },
  });
  await flushPromises();
  return { w: wrapper, store };
}

const dialog = () => document.body.querySelector("[data-test=isa-approve]")!;
const button = (name: string) =>
  Array.from(dialog().querySelectorAll<HTMLButtonElement>("button")).find(b => b.textContent?.trim() === name)!;

describe("IsaApproveDialog", () => {
  it("says what approving does before it starts", async () => {
    await render();
    expect(dialog().textContent).toContain("Approve My study plan?");
    expect(dialog().textContent).toContain("Its SEEK project is created from the ISA tree");
    expect(dialog().textContent).toContain("1 bundled item: ds-new");
  });

  it("follows the approval's stages to the end", async () => {
    vi.useFakeTimers();
    await render();
    button("Approve").click();
    await flushPromises();
    expect(dialog().textContent).toContain("Creating the SEEK project");
    await vi.advanceTimersByTimeAsync(APPROVE_STEP);
    expect(dialog().textContent).toContain("Registering ds-new");
    await vi.runAllTimersAsync();
    expect(dialog().textContent).toContain("My study plan is in the platform.");
  });

  it("keeps approving after it is closed, as on the other hubs", async () => {
    vi.useFakeTimers();
    const { w, store } = await render();
    button("Approve").click();
    await flushPromises();
    button("Close").click();
    expect(w.emitted("update:modelValue")).toEqual([[false]]);
    await vi.runAllTimersAsync();
    expect(store.entries.find(e => e.project.project.id === "p-mine")!.approval).toEqual({ state: "approved" });
  });
});
