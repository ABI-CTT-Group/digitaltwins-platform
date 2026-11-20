import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";
import { testVuetify } from "@/testing/vuetify";

const route = reactive({ query: {} as Record<string, string> });
const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("vue-router", () => ({ useRoute: () => route, useRouter: () => router }));
const api = vi.hoisted(() => ({ useDashboardProgrammes: vi.fn(), useDashboardCategoryChildren: vi.fn() }));
vi.mock("@/bootstrap/dashboard_api", () => api);

import StudyDashboardPrototype from "../StudyDashboardPrototype.vue";

const render = () => mount(StudyDashboardPrototype, {
  global: { plugins: [testVuetify()], stubs: { DashboardHeader: true, LevelGrid: true, StudyDesign: true } },
});

beforeEach(() => {
  vi.resetAllMocks();
  setActivePinia(createPinia());
});

describe("StudyDashboardPrototype", () => {
  it("starts at the one Te Whatu Ora Radiology Reporting programme, without the API", async () => {
    route.query = {};
    const w = render();
    await flushPromises();
    expect(w.findComponent({ name: "DashboardHeader" }).props("rootLabel")).toBe("Study dashboard");
    expect(w.findComponent({ name: "LevelGrid" }).props("items").map((i: { name: string }) => i.name)).toEqual(["Te Whatu Ora Radiology Reporting"]);
    expect(w.text()).not.toMatch(/prototype|kept in this browser/i);
    expect(api.useDashboardProgrammes).not.toHaveBeenCalled();
    expect(api.useDashboardCategoryChildren).not.toHaveBeenCalled();
  });

  it("shows a study as one study design, not assay cards", async () => {
    route.query = { trail: "te-whatu-ora-radiology-reporting,te-whatu-ora-radiology-reporting:p-breast,te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report,te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot" };
    const w = render();
    await flushPromises();
    expect(w.findComponent({ name: "StudyDesign" }).props()).toEqual({ projectId: "p-breast", studyId: "s-breast-pilot" });
    expect(w.findComponent({ name: "LevelGrid" }).exists()).toBe(false);
  });

  it("shortens a trail it can't resolve", async () => {
    route.query = { trail: "te-whatu-ora-radiology-reporting,te-whatu-ora-radiology-reporting:gone" };
    render();
    await flushPromises();
    expect(router.push).toHaveBeenCalledWith({ query: { trail: "te-whatu-ora-radiology-reporting" } });
  });
});
