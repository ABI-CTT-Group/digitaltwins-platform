import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";
import { testVuetify } from "@/testing/vuetify";

const route = reactive({ meta: { type: "study" }, query: {} as Record<string, string> });
vi.mock("vue-router", () => ({ useRoute: () => route, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
const api = vi.hoisted(() => ({ useDashboardProgrammes: vi.fn(), useDashboardCategoryChildren: vi.fn() }));
vi.mock("@/bootstrap/dashboard_api", () => api);
const loadAssayList = vi.fn();
vi.mock("@/composables/useAssayActions", () => ({ useAssayActions: () => ({ loadAssayList }) }));

import DashboardView from "../DashboardView.vue";
import { clearDashboardCache } from "@/composables/useDashboardData";

const render = () => mount(DashboardView, {
  global: { plugins: [testVuetify()], stubs: { DashboardHeader: true, LevelGrid: true } },
});

beforeEach(() => {
  vi.resetAllMocks();
  clearDashboardCache();
  setActivePinia(createPinia());
  api.useDashboardProgrammes.mockResolvedValue([{ seekId: "7", name: "Lungs", category: "Programmes" }]);
});

describe("DashboardView", () => {
  it("shows the assay cards for a study", async () => {
    api.useDashboardCategoryChildren.mockImplementation(async (id: string) =>
      [{ seekId: String(Number(id) + 1), name: `n${id}`, category: "x" }]);
    route.query = { trail: "7,8,9,10" };
    const w = render();
    await flushPromises();
    expect(w.findComponent({ name: "LevelGrid" }).exists()).toBe(true);
    expect(loadAssayList).toHaveBeenCalled();
  });
});
