import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const api = vi.hoisted(() => ({ useDashboardProgrammes: vi.fn(), useDashboardCategoryChildren: vi.fn() }));
const auth = vi.hoisted(() => ({ hasAdminRole: true }));
vi.mock("@/bootstrap/dashboard_api", () => api);
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => auth }));

import { clearDashboardCache, describeCategory, useDashboardData } from "../useDashboardData";

const all = () => true;

beforeEach(() => {
  vi.resetAllMocks();
  clearDashboardCache();
  setActivePinia(createPinia());
  auth.hasAdminRole = true;
  api.useDashboardProgrammes.mockResolvedValue([{ seekId: "7", name: "Lungs", category: "Programmes" }]);
  api.useDashboardCategoryChildren.mockResolvedValue([{ seekId: "8", name: "Project A", category: "Projects" }]);
});

describe("useDashboardData: study design sandbox (prototype)", () => {
  it("adds the sandbox programme for an admin", async () => {
    const { items } = await useDashboardData().loadTrail([], all);
    expect(items.map(i => i.name)).toEqual(["Lungs", "Study design sandbox"]);
  });

  it("hides it from everyone else", async () => {
    auth.hasAdminRole = false;
    const { items } = await useDashboardData().loadTrail([], all);
    expect(items.map(i => i.name)).toEqual(["Lungs"]);
  });

  it("walks a sandbox trail from the browser's store, never the API", async () => {
    const r = await useDashboardData().loadTrail(["isa-sandbox", "isa-sandbox:p-breast-pilot", "isa-sandbox:p-breast-pilot:i-breast"], all);
    expect(r.breadcrumbs.map(b => b.name)).toEqual(["Study design sandbox", "Breast pilot (example)", "Breast cancer imaging"]);
    expect(r.currentCategory).toBe("Studies");
    expect(r.items.map(i => i.name)).toEqual(["Breast pilot"]);
    expect(api.useDashboardCategoryChildren).not.toHaveBeenCalled();
  });

  it("leaves real programmes on the API and its cache", async () => {
    const data = useDashboardData();
    const r = await data.loadTrail(["7"], all);
    expect(r.items.map(i => i.name)).toEqual(["Project A"]);
    await data.loadTrail(["7"], all);
    expect(api.useDashboardCategoryChildren).toHaveBeenCalledTimes(1);
    expect(api.useDashboardCategoryChildren).toHaveBeenCalledWith("7", "Programmes");
    expect(api.useDashboardProgrammes).toHaveBeenCalledTimes(1);
  });
});

describe("describeCategory", () => {
  it("says an assay is configured once and can run many times", () => {
    expect(describeCategory("Assays")).toBe("An Assay is a workflow configured to run against a study cohort. It can be run many times.");
  });
});
