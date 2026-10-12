import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  useUploadInit: vi.fn(), useUploadFinalize: vi.fn(), useUploadStatus: vi.fn(), useUploadCancel: vi.fn(),
}));
const dtApiAxios = vi.hoisted(() => ({ put: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ dtApiAxios }));
vi.mock("@/bootstrap/measurement_api", () => ({
  ...api,
  splitMeasurementId: (id: string) => ({ kind: "upload", rawId: id.replace(/^upload:/, "") }),
}));

import { ChunkedUploader, loadPendingUploads } from "@/bootstrap/measurement_upload";

function folder(name: string) {
  const file = new File(["weights"], "checkpoint.pth");
  Object.defineProperty(file, "webkitRelativePath", { value: `${name}/primary/checkpoint.pth` });
  return { kind: "folder" as const, files: [file], rootName: name, fileCount: 1, totalSize: file.size };
}

function savePending(id: string, extra: Record<string, unknown> = {}) {
  localStorage.setItem(`measurement.upload.${id}`,
    JSON.stringify({ measurementId: id, name: id, sourceKind: "folder", manifest: [], ...extra }));
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
});

describe("ChunkedUploader", () => {
  it("creates the session in its category and remembers it while uploading", async () => {
    api.useUploadInit.mockResolvedValue({ measurementId: "upload:u1", maxPartSize: 8 });
    let pendingDuringUpload: unknown[] = [];
    dtApiAxios.put.mockImplementation(async () => { pendingDuringUpload = loadPendingUploads("models"); });
    api.useUploadFinalize.mockResolvedValue({ id: "upload:u1" });

    await new ChunkedUploader(folder("model_skin_test"), { name: "Skin", category: "models" }).start();

    expect(api.useUploadInit.mock.calls[0][0]).toMatchObject({ name: "Skin", category: "models" });
    expect(pendingDuringUpload).toMatchObject([{ measurementId: "upload:u1", category: "models" }]);
  });

  it("defaults to measurements", async () => {
    api.useUploadInit.mockResolvedValue({ measurementId: "upload:u2", maxPartSize: 8 });
    api.useUploadFinalize.mockResolvedValue({ id: "upload:u2" });

    await new ChunkedUploader(folder("m"), { name: "M" }).start();

    expect(api.useUploadInit.mock.calls[0][0].category).toBe("measurements");
  });
});

describe("loadPendingUploads", () => {
  it("filters by category; entries saved before categories existed are measurements", () => {
    savePending("upload:old");
    savePending("upload:m", { category: "measurements" });
    savePending("upload:model", { category: "models" });

    expect(loadPendingUploads("models").map((p) => p.measurementId)).toEqual(["upload:model"]);
    expect(loadPendingUploads("measurements").map((p) => p.measurementId).sort())
      .toEqual(["upload:m", "upload:old"]);
    expect(loadPendingUploads()).toHaveLength(3);
  });
});
