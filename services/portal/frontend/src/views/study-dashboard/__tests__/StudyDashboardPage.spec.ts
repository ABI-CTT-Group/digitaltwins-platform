import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";
import { testVuetify } from "@/testing/vuetify";

const route = reactive({ query: {} as Record<string, string> });
const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("vue-router", () => ({ useRoute: () => route, useRouter: () => router }));
const auth = reactive({ hasAdminRole: false, hasResearcherRole: false, hasClinicianRole: false });
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => auth }));

import StudyDashboardPage from "../StudyDashboardPage.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
  router.push.mockReset();
  route.query = {};
  Object.assign(auth, { hasAdminRole: false, hasResearcherRole: false, hasClinicianRole: false });
});

async function render() {
  wrapper = mount(StudyDashboardPage, {
    global: {
      plugins: [testVuetify()],
      stubs: { RouterLink: RouterLinkStub, DashboardHeader: true, LevelGrid: true, StudyDesign: true },
    },
  });
  await flushPromises();
  return wrapper;
}

const studyList = (w: VueWrapper) => w.find("[data-test=study-row]").exists();
const programmes = (w: VueWrapper) => w.findComponent({ name: "LevelGrid" }).exists();
const switcher = (w: VueWrapper) => w.find("[data-test=view-as]");
const chosen = (w: VueWrapper) =>
  (["clinician", "researcher"] as const).find(v => (w.find(`[data-test=view-as-${v}]`).element as HTMLInputElement).checked);

describe("StudyDashboardPage", () => {
  it("shows a clinician their studies to review, with no switch", async () => {
    auth.hasClinicianRole = true;
    const w = await render();
    expect(studyList(w)).toBe(true);
    expect(programmes(w)).toBe(false);
    expect(switcher(w).exists()).toBe(false);
  });

  it("shows a researcher the programmes, with no switch", async () => {
    auth.hasResearcherRole = true;
    const w = await render();
    expect(programmes(w)).toBe(true);
    expect(studyList(w)).toBe(false);
    expect(switcher(w).exists()).toBe(false);
  });

  it("lets an admin view as either, starting as a researcher", async () => {
    auth.hasAdminRole = true;
    const w = await render();
    expect(switcher(w).text()).toContain("View as");
    expect(switcher(w).text()).toContain("Clinician");
    expect(switcher(w).text()).toContain("Researcher");
    expect(chosen(w)).toBe("researcher");
    expect(programmes(w)).toBe(true);
  });

  it("switches to the clinician view at its top level, and remembers it", async () => {
    auth.hasAdminRole = true;
    route.query = { trail: "te-whatu-ora-radiology-reporting" };
    const w = await render();
    await w.find("[data-test=view-as-clinician]").setValue(true);
    await flushPromises();
    expect(router.push).toHaveBeenCalledWith({ name: "StudyDashboardPrototype", query: { view: "clinician" } });
    route.query = { view: "clinician" };
    await flushPromises();
    expect(studyList(w)).toBe(true);
    expect(chosen(w)).toBe("clinician");

    w.unmount();
    route.query = {};
    const again = await render();
    expect(chosen(again)).toBe("clinician");
  });

  it("opens the researcher view for a link into a programme", async () => {
    auth.hasAdminRole = true;
    localStorage.setItem("study-dashboard-view", "clinician");
    route.query = { trail: "te-whatu-ora-radiology-reporting" };
    const w = await render();
    expect(chosen(w)).toBe("researcher");
    expect(programmes(w)).toBe(true);
  });
});
