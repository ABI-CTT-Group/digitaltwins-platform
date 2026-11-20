import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ useDashboardProgrammes: vi.fn(), useDashboardCategoryChildren: vi.fn() }));
vi.mock("@/bootstrap/dashboard_api", () => api);

import { clearDashboardCache, describeCategory, useDashboardData } from "../useDashboardData";

const all = () => true;

beforeEach(() => {
  vi.resetAllMocks();
  clearDashboardCache();
  api.useDashboardProgrammes.mockResolvedValue([{ seekId: "7", name: "Lungs", category: "Programmes" }]);
  api.useDashboardCategoryChildren.mockResolvedValue([{ seekId: "8", name: "Project A", category: "Projects" }]);
});

describe("useDashboardData", () => {
  it("shows only the API's programmes", async () => {
    const { items } = await useDashboardData().loadTrail([], all);
    expect(items.map(i => i.name)).toEqual(["Lungs"]);
  });

  it("doesn't resolve a trail into the ISA projects prototype", async () => {
    const r = await useDashboardData().loadTrail(["te-whatu-ora-radiology-reporting", "te-whatu-ora-radiology-reporting:p-breast"], all);
    expect(r.breadcrumbs).toEqual([]);
    expect(r.currentCategory).toBe("Programmes");
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
