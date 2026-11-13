import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";

const toast = { success: vi.fn(), warning: vi.fn(), info: vi.fn(), error: vi.fn() };
vi.mock("vue-toastification", () => ({ useToast: () => toast }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ displayName: "Dr A. Reader" }) }));

import WorklistsView from "../WorklistsView.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
  Object.values(toast).forEach(f => f.mockClear());
});

async function render(studyId = "breast-mri-reading") {
  wrapper = mount(WorklistsView, {
    props: { studyId },
    global: { plugins: [testVuetify()], stubs: { RouterLink: RouterLinkStub } },
  });
  await flushPromises();
  return wrapper;
}

const panel = (w: VueWrapper) => w.find("[data-test=review-panel]");
const click = async (w: VueWrapper, sel: string) => { await w.find(sel).trigger("click"); await flushPromises(); };

describe("WorklistsView", () => {
  it("names the study and links back to all studies", async () => {
    const w = await render();
    expect(w.find("[data-test=study-title]").text()).toBe("Breast MRI reading");
    const back = w.findComponent(RouterLinkStub);
    expect(back.props("to")).toEqual({ name: "ClinicianDashboard" });
    expect(back.text()).toContain("All studies");
  });

  it("says when there is no such study", async () => {
    const w = await render("no-such-study");
    expect(w.text()).toContain("There is no study called no-such-study.");
    expect(w.find("[data-test=progress]").exists()).toBe(false);
  });

  it("shows progress and the count on each tab", async () => {
    const w = await render();
    expect(w.find("[data-test=progress]").text()).toBe("15 of 36 cases reviewed");
    expect(w.find("[data-test=tab-review]").text()).toBe("To review21");
    expect(w.find("[data-test=tab-needs]").text()).toBe("Needs correction3");
    expect(w.findAll("[data-test=case-row]")).toHaveLength(21);
  });

  it("starts a batch of 10 from the first case to review", async () => {
    const w = await render();
    expect((w.find("#batch-size").element as HTMLInputElement).value).toBe("10");
    await w.find("[data-test=batch-form]").trigger("submit");
    await flushPromises();
    expect(panel(w).find("h2").text()).toBe("sub-013");
    expect(panel(w).text()).toContain("Case 1 of 10 in this batch");
  });

  it("confirms a case and moves to the next one in the batch", async () => {
    const w = await render();
    await w.find("[data-test=batch-form]").trigger("submit");
    await click(w, "[data-test=confirm]");
    expect(toast.success).toHaveBeenCalledWith("Confirmed sub-013");
    expect(panel(w).find("h2").text()).toBe("sub-016");
    expect(panel(w).text()).toContain("Case 2 of 10 in this batch");
    expect(w.find("[data-test=progress]").text()).toBe("16 of 36 cases reviewed");
  });

  it("needs a note before sending a case for correction", async () => {
    const w = await render();
    await w.find("[data-test=batch-form]").trigger("submit");
    await click(w, "[data-test=flag]");
    await w.find("[data-test=flag-form]").trigger("submit");
    await flushPromises();
    expect(toast.warning).toHaveBeenCalled();
    expect(panel(w).find("h2").text()).toBe("sub-013");

    await w.find("#flag-note").setValue("Contour misses the lower margin");
    await w.find("[data-test=flag-form]").trigger("submit");
    await flushPromises();
    expect(toast.success).toHaveBeenCalledWith("Sent sub-013 for correction");
    expect(panel(w).find("h2").text()).toBe("sub-016");
    expect(w.find("[data-test=tab-needs]").text()).toBe("Needs correction4");
  });

  it("leaves the batch when a case is picked from the list", async () => {
    const w = await render();
    await w.find("[data-test=batch-form]").trigger("submit");
    await flushPromises();
    await w.findAll("[data-test=case-row]")[3].trigger("click");
    await flushPromises();
    expect(panel(w).find("h2").text()).toBe("sub-019");
    expect(panel(w).text()).not.toContain("in this batch");
  });
});
