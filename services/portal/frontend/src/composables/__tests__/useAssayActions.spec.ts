import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { AssayDetails, DashboardCategory } from "@/models/types";

const api = vi.hoisted(() => ({
  useDashboardGetAssayConfigDetails: vi.fn(),
  useDashboardWorkflowDetail: vi.fn(),
  useDashboardGetAssayLaunch: vi.fn(),
  useSaveAssayDetails: vi.fn(),
  useDashboardSubmitAssayResults: vi.fn(),
  useDashboardDownloadAssayWorkspace: vi.fn(),
}));
vi.mock("@/bootstrap/dashboard_api", () => api);
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() }) }));

import { useAssayActions } from "../useAssayActions";

const assay = (seekId: string, extra: Partial<DashboardCategory> = {}): DashboardCategory => ({
  seekId, name: `Assay ${seekId}`, category: "Assays", ...extra,
});

const saved = (seekId: string): AssayDetails => ({
  seekId, uuid: "u", numberOfParticipants: [1], isAssayReadyToLaunch: true,
  workflow: { uuid: "", seekId: "39", name: "Workflow - Inference", inputs: [], outputs: [] },
});

beforeEach(() => {
  vi.resetAllMocks();
  setActivePinia(createPinia());
});

describe("useAssayActions.loadAssayList", () => {
  it("gives an assay with no linked workflow an empty workflow to pick from", async () => {
    api.useDashboardGetAssayConfigDetails.mockResolvedValue(null);
    const actions = useAssayActions();

    await actions.loadAssayList([assay("42", { tag: "script" })]);

    expect(api.useDashboardWorkflowDetail).not.toHaveBeenCalled();
    expect(actions.assayDetails.value["42"].workflow).toEqual({
      uuid: "", seekId: "", name: "", type: "script", inputs: [], outputs: [],
    });
  });

  it("keeps loading the other assays when one fails", async () => {
    api.useDashboardGetAssayConfigDetails
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(saved("43"));
    const actions = useAssayActions();

    await actions.loadAssayList([assay("42"), assay("43")]);

    expect(actions.assayDetails.value["43"]).toEqual(saved("43"));
  });
});

describe("useAssayActions.openEdit", () => {
  it("edits a copy, so cancelling leaves the cached config alone", async () => {
    api.useDashboardGetAssayConfigDetails.mockResolvedValue(saved("42"));
    const actions = useAssayActions();
    await actions.loadAssayList([assay("42")]);

    actions.openEdit("42");
    actions.currentAssayDetails.value!.workflow.seekId = "40";

    expect(actions.assayDetails.value["42"].workflow.seekId).toBe("39");
  });
});

describe("useAssayActions.save", () => {
  it("saves the config as ready to launch, so Launch stays enabled after a reload", async () => {
    api.useDashboardGetAssayConfigDetails.mockResolvedValue({ ...saved("42"), isAssayReadyToLaunch: false });
    // Record what is sent at call time: save() mutates the same object afterwards.
    const sent: boolean[] = [];
    api.useSaveAssayDetails.mockImplementation(async (d: AssayDetails) => {
      sent.push(d.isAssayReadyToLaunch);
      return true;
    });
    const actions = useAssayActions();
    await actions.loadAssayList([assay("42")]);
    actions.openEdit("42");

    await actions.save();

    expect(sent).toEqual([true]);
    expect(actions.assayDetails.value["42"].isAssayReadyToLaunch).toBe(true);
  });

  it("leaves the assay not ready when the save fails", async () => {
    api.useDashboardGetAssayConfigDetails.mockResolvedValue({ ...saved("42"), isAssayReadyToLaunch: false });
    api.useSaveAssayDetails.mockRejectedValue(new Error("502"));
    const actions = useAssayActions();
    await actions.loadAssayList([assay("42")]);
    actions.openEdit("42");

    await actions.save();

    expect(actions.assayDetails.value["42"].isAssayReadyToLaunch).toBe(false);
  });
});
