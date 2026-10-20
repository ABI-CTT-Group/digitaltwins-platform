import { beforeEach, describe, expect, it, vi } from "vitest";

const { dtApi, dtApiAxios } = vi.hoisted(() => ({
  dtApi: { get: vi.fn(), post: vi.fn() },
  dtApiAxios: { get: vi.fn() },
}));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi, dtApiAxios }));

import {
  useDashboardDownloadAssayWorkspace,
  useDashboardGetAssayLaunch,
  useDashboardProgrammes,
  useDashboardSubmitAssayResults,
  useSaveAssayDetails,
} from "@/bootstrap/dashboard_api";

beforeEach(() => vi.resetAllMocks());

// The dashboard is served by the platform API (/api/dashboard), not the builder.
describe("dashboard api", () => {
  it("reads through the platform API", async () => {
    dtApi.get.mockResolvedValue([]);
    await useDashboardProgrammes();
    await useDashboardGetAssayLaunch("43");
    expect(dtApi.get.mock.calls).toEqual([
      ["/dashboard/programmes"],
      ["/dashboard/assay-launch", { seekId: "43" }],
    ]);
  });

  it("writes through the platform API", async () => {
    dtApi.post.mockResolvedValue(true);
    await useSaveAssayDetails({} as any);
    await useDashboardSubmitAssayResults("38");
    expect(dtApi.post.mock.calls).toEqual([
      ["/dashboard/assay-details", {}],
      ["/dashboard/assay-results-submit?seek_id=38"],
    ]);
  });

  it("downloads the results zip from the platform API", async () => {
    dtApiAxios.get.mockResolvedValue({ data: "zip", headers: { "content-disposition": 'attachment; filename="r.zip"' } });
    const res = await useDashboardDownloadAssayWorkspace("38");
    expect(dtApiAxios.get).toHaveBeenCalledWith("/dashboard/assay-download",
      { params: { seek_id: "38" }, responseType: "blob" });
    expect(res).toEqual({ data: "zip", filename: "r.zip" });
  });
});
