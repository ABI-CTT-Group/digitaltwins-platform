import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  useToolApproval: vi.fn(), useToolApprovalStatus: vi.fn(), usePlatformDataset: vi.fn(),
  useWorkflowPlatformApproval: vi.fn(), useWorkflowApprovalStatus: vi.fn(),
  useMeasurementSubmit: vi.fn(), useGetMeasurement: vi.fn(),
}));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({
  useToolApproval: api.useToolApproval, useToolApprovalStatus: api.useToolApprovalStatus, usePlatformDataset: api.usePlatformDataset,
}));
vi.mock("@/bootstrap/workflow_api", () => ({
  useWorkflowPlatformApproval: api.useWorkflowPlatformApproval, useWorkflowApprovalStatus: api.useWorkflowApprovalStatus,
}));
vi.mock("@/bootstrap/measurement_api", () => ({ useMeasurementSubmit: api.useMeasurementSubmit, useGetMeasurement: api.useGetMeasurement }));

import { approveAdapter, fhirHint } from "../approveAdapters";

const TOOL = { id: "t1", name: "curator" } as any;
beforeEach(() => vi.resetAllMocks());

describe("tool and workflow approval", () => {
  it("hands the latest build to the platform in a SEEK project, publishing FHIR only with an annotation", async () => {
    api.useToolApproval.mockResolvedValue({ handoffStatus: "uploading", partsSent: 1, partsTotal: 4 });
    const p = await approveAdapter("tools").start({ ...TOOL, hasAnnotation: true }, 11);
    expect(api.useToolApproval).toHaveBeenCalledWith("t1", { seekProjectId: 11, fhir: true });
    await approveAdapter("tools").start(TOOL, 11);
    expect(api.useToolApproval).toHaveBeenLastCalledWith("t1", { seekProjectId: 11, fhir: false });
    expect(p).toEqual({ state: "running", stage: "Uploading the build", percent: 25 });
    expect(approveAdapter("tools").needsProject).toBe(true);
  });

  it("uses the workflow endpoints for a workflow", async () => {
    api.useWorkflowPlatformApproval.mockResolvedValue({ handoffStatus: "committing" });
    api.useWorkflowApprovalStatus.mockResolvedValue({ handoffStatus: "committing" });
    const adapter = approveAdapter("workflows");
    expect(await adapter.start({ id: "w1" } as any, 3)).toMatchObject({ state: "running" });
    expect(api.useWorkflowPlatformApproval).toHaveBeenCalledWith("w1", { seekProjectId: 3, fhir: false });
    await adapter.poll({ id: "w1" } as any);
    expect(api.useWorkflowApprovalStatus).toHaveBeenCalledWith("w1");
    expect(api.useToolApprovalStatus).not.toHaveBeenCalled();
  });

  it.each([
    [{ handoffStatus: "committing" }, { state: "running", stage: "Registering it in SEEK and storing it in the platform" }],
    [{ handoffStatus: "awaiting_reauth" }, { state: "waiting", stage: "Waiting for you to sign in again" }],
    [{ handoffStatus: "failed", handoffError: "SEEK 403" }, { state: "failed", stage: "Approval failed", error: "SEEK 403" }],
  ])("reads a handoff %j as %j", async (status, progress) => {
    api.useToolApprovalStatus.mockResolvedValue(status);
    expect(await approveAdapter("tools").poll(TOOL)).toEqual(progress);
  });

  it("follows the FHIR push once the build is in the platform", async () => {
    api.useToolApprovalStatus.mockResolvedValue({ handoffStatus: "completed", datasetUuid: "d1" });
    const poll = () => approveAdapter("tools").poll(TOOL);

    api.usePlatformDataset.mockResolvedValue({ fhirStatus: "pushing" });
    expect(await poll()).toEqual({ state: "running", stage: "Publishing to FHIR" });
    api.usePlatformDataset.mockResolvedValue({ fhirStatus: "completed" });
    expect(await poll()).toEqual({ state: "done", stage: "In the platform" });
    api.usePlatformDataset.mockResolvedValue({ fhirStatus: "failed", fhirFailureMessage: "HAPI 500" });
    expect(await poll()).toEqual({ state: "done", stage: "In the platform", fhirError: "HAPI 500" });
  });
});

describe("measurement and model approval", () => {
  const M = { id: "upload:m1", name: "scans" } as any;

  it("commits the staged upload, with no SEEK project", async () => {
    api.useMeasurementSubmit.mockResolvedValue({ ...M, status: "uploading" });
    expect(await approveAdapter("measurements").start(M)).toEqual({ state: "running", stage: "Storing it in the platform" });
    expect(api.useMeasurementSubmit).toHaveBeenCalledWith("upload:m1");
    expect(approveAdapter("models").needsProject).toBe(false);
  });

  it.each([
    [{ status: "uploading", uuid: "d1" }, { state: "running", stage: "Publishing to FHIR" }],
    [{ status: "completed", uuid: "d1" }, { state: "done", stage: "In the platform" }],
    [{ status: "fhir_failed", uuid: "d1", failureMessage: "HAPI 500" }, { state: "done", stage: "In the platform", fhirError: "HAPI 500" }],
    [{ status: "submit_failed", failureMessage: "disk full" }, { state: "failed", stage: "Approval failed", error: "disk full" }],
  ])("reads a dataset %j as %j", async (row, progress) => {
    api.useGetMeasurement.mockResolvedValue({ ...M, ...row });
    expect(await approveAdapter("models").poll(M)).toEqual(progress);
    expect(api.useGetMeasurement).toHaveBeenCalledWith("upload:m1");
  });
});

describe("fhirHint", () => {
  it("says nothing is published to FHIR without an annotation, and nothing for an annotated item", () => {
    for (const category of ["tools", "workflows"] as const) {
      expect(fhirHint(category, { hasAnnotation: false }))
        .toBe("No FHIR annotation, so nothing is published to FHIR. To publish it, add one before approving.");
    }
    expect(fhirHint("measurements", {})).toBe("No FHIR annotation, so nothing is published to FHIR. To publish it, add one before approving.");
    expect(fhirHint("models", {})).toBe("No FHIR annotation, so nothing is published to FHIR. You can add one later from its card.");
    expect(fhirHint("models", { hasAnnotation: true })).toBeUndefined();
  });
});
