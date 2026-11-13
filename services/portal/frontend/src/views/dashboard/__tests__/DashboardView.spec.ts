import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";
import { testVuetify } from "@/testing/vuetify";

const route = reactive({ meta: { type: "study" }, query: {} as Record<string, string> });
vi.mock("vue-router", () => ({ useRoute: () => route, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
const api = vi.hoisted(() => ({ useDashboardProgrammes: vi.fn(), useDashboardCategoryChildren: vi.fn() }));
vi.mock("@/bootstrap/dashboard_api", () => api);
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ hasAdminRole: true }) }));
const loadAssayList = vi.fn();
vi.mock("@/composables/useAssayActions", () => ({ useAssayActions: () => ({ loadAssayList }) }));

import DashboardView from "../DashboardView.vue";
import { clearDashboardCache } from "@/composables/useDashboardData";

const render = () => mount(DashboardView, {
  global: { plugins: [testVuetify()], stubs: { DashboardHeader: true, LevelGrid: true, StudyDesign: true } },
});

beforeEach(() => {
  vi.resetAllMocks();
  clearDashboardCache();
  setActivePinia(createPinia());
  api.useDashboardProgrammes.mockResolvedValue([{ seekId: "7", name: "Lungs", category: "Programmes" }]);
});

describe("DashboardView: study design sandbox (prototype)", () => {
  it("shows a sandbox study as one study design, not assay cards", async () => {
    route.query = { trail: "isa-sandbox,isa-sandbox:p-test-project,isa-sandbox:p-test-project:i-test,isa-sandbox:p-test-project:i-test:s-test" };
    const w = render();
    await flushPromises();
    expect(w.findComponent({ name: "StudyDesign" }).props()).toEqual({ projectId: "p-test-project", studyId: "s-test" });
    expect(w.findComponent({ name: "LevelGrid" }).exists()).toBe(false);
    expect(loadAssayList).not.toHaveBeenCalled();
  });

  it("keeps the assay cards for a real study", async () => {
    api.useDashboardCategoryChildren.mockImplementation(async (id: string) =>
      [{ seekId: String(Number(id) + 1), name: `n${id}`, category: "x" }]);
    route.query = { trail: "7,8,9,10" };
    const w = render();
    await flushPromises();
    expect(w.findComponent({ name: "StudyDesign" }).exists()).toBe(false);
    expect(w.findComponent({ name: "LevelGrid" }).exists()).toBe(true);
    expect(loadAssayList).toHaveBeenCalled();
  });
});
