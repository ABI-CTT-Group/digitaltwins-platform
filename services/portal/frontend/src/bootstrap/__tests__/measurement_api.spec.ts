import { beforeEach, describe, expect, it, vi } from "vitest";

const dtApi = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi }));

import { useMeasurement, useUploadInit } from "@/bootstrap/measurement_api";

beforeEach(() => vi.resetAllMocks());

describe("useMeasurement", () => {
  it("lists only measurement upload sessions next to measurement datasets", async () => {
    dtApi.get.mockImplementation(async (path: string) =>
      path === "/datasets/uploads" ? { uploads: [] } : { datasets: [] });

    await useMeasurement();

    expect(dtApi.get).toHaveBeenCalledWith("/datasets/uploads", { category: "measurements" });
    expect(dtApi.get).toHaveBeenCalledWith("/datasets", { categories: "measurements" });
  });
});

describe("useUploadInit", () => {
  const payload = { name: "n", sourceKind: "folder" as const, manifest: [] };

  it("creates a staged measurements session by default", async () => {
    dtApi.post.mockResolvedValue({ uploadId: "u1", maxPartSize: 8 });

    expect(await useUploadInit(payload)).toEqual({ measurementId: "upload:u1", maxPartSize: 8 });
    expect(dtApi.post).toHaveBeenCalledWith("/datasets/uploads",
      { ...payload, category: "measurements", commitMode: "on_approve" });
  });

  it("creates a session of the given category", async () => {
    dtApi.post.mockResolvedValue({ uploadId: "u2", maxPartSize: 8 });

    await useUploadInit({ ...payload, category: "models" });

    expect(dtApi.post.mock.calls[0][1]).toMatchObject({ category: "models", commitMode: "on_approve" });
  });
});
