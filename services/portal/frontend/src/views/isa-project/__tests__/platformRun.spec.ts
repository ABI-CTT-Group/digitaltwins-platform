import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const api = vi.hoisted(() => ({
  useDashboardGetAssayLaunch: vi.fn(),
  useDashboardSubmitAssayResults: vi.fn(),
  useDashboardGetAssayConfigDetails: vi.fn(),
  useDashboardGetDatasets: vi.fn(),
}));
const toast = vi.hoisted(() => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn(), info: vi.fn() }));
vi.mock("@/bootstrap/dashboard_api", () => api);
vi.mock("vue-toastification", () => ({ useToast: () => toast }));

import { useDashboardCacheStore } from "@/store/dashboard_cache_store";
import { launchPlatformAssay, platformAssayIds, platformInputsExist, submitPlatformAssay } from "../platformRun";
import type { IsaProjectEntry } from "../sandbox";

const entry = (extra: Partial<IsaProjectEntry>): IsaProjectEntry => ({
  project: { schemaVersion: "0.1-draft", project: { id: "p", title: "P" }, investigations: [] },
  source: "example",
  ...extra,
});

let open: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.resetAllMocks();
  setActivePinia(createPinia());
  open = vi.fn();
  vi.stubGlobal("open", open);
});

describe("platformAssayIds", () => {
  it("links the example's assays to the platform's Test Project assays and mock assays", () => {
    expect(platformAssayIds(entry({ exampleId: "example-breast-pilot" }))).toEqual({
      "a-cohort": "41", "a-convert": "42", "a-initial-inference": "46", "a-breast-app": "45", "a-finetune": "47",
      "a-inference": "48", "a-breast-model": "49", "a-lesion-report": "45", "a-statistics": "50", "a-visualise": "43",
      "a-pipeline-cohort": "41", "a-pipeline-convert": "42", "a-pipeline-visualise": "43", "a-pipeline-breast-app": "45",
    });
  });

  it("links nothing else", () => {
    expect(platformAssayIds(entry({ source: "upload" }))).toEqual({});
    expect(platformAssayIds(entry({ source: "upload", exampleId: "example-breast-pilot" }))).toEqual({});
    expect(platformAssayIds(entry({ exampleId: "another-example" }))).toEqual({});
    expect(platformAssayIds(undefined)).toEqual({});
  });
});

describe("launchPlatformAssay", () => {
  it("starts a script run and keeps its Airflow page for Monitor", async () => {
    api.useDashboardGetAssayLaunch.mockResolvedValue({ type: "airflow", data: "http://airflow/dags/workflow_116" });
    expect(await launchPlatformAssay("42")).toBe(true);
    expect(api.useDashboardGetAssayLaunch).toHaveBeenCalledWith("42");
    expect(useDashboardCacheStore().assayExecute["42"]).toEqual({ text: "Monitor", url: "http://airflow/dags/workflow_116" });
    expect(toast.success).toHaveBeenCalled();
    expect(open).not.toHaveBeenCalled();
  });

  it("opens a notebook's workspace, and keeps it for Monitor", async () => {
    api.useDashboardGetAssayLaunch.mockResolvedValue({ type: "notebook", data: "http://hub/lab/tree/assay_41" });
    expect(await launchPlatformAssay("41")).toBe(true);
    expect(open).toHaveBeenCalledWith("http://hub/lab/tree/assay_41", "_blank");
    expect(useDashboardCacheStore().assayExecute["41"].url).toBe("http://hub/lab/tree/assay_41");
  });

  it("opens a GUI tool", async () => {
    api.useDashboardGetAssayLaunch.mockResolvedValue({ type: "gui", data: "/tool-view?assay=43" });
    expect(await launchPlatformAssay("43")).toBe(true);
    expect(open).toHaveBeenCalledWith("/tool-view?assay=43", "_blank");
  });

  it("reports a launch that didn't start", async () => {
    api.useDashboardGetAssayLaunch.mockResolvedValueOnce(null);
    expect(await launchPlatformAssay("42")).toBe(false);
    expect(toast.warning).toHaveBeenCalled();

    api.useDashboardGetAssayLaunch.mockResolvedValueOnce({ message: "Airflow is disabled" });
    expect(await launchPlatformAssay("42")).toBe(false);
    expect(toast.info).toHaveBeenCalledWith("Airflow is disabled", expect.anything());

    api.useDashboardGetAssayLaunch.mockRejectedValueOnce({ response: { status: 500 } });
    expect(await launchPlatformAssay("42")).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("Launch failed: server error, please try again later.");
  });
});

describe("submitPlatformAssay", () => {
  it("uploads the run's workspace as datasets", async () => {
    api.useDashboardSubmitAssayResults.mockResolvedValue({ message: "Successfully uploaded 1 datasets." });
    expect(await submitPlatformAssay("41")).toBe(true);
    expect(api.useDashboardSubmitAssayResults).toHaveBeenCalledWith("41");
    expect(toast.success).toHaveBeenCalled();
  });

  it("reports a submit that failed", async () => {
    api.useDashboardSubmitAssayResults.mockRejectedValue({ response: { status: 404 } });
    expect(await submitPlatformAssay("43")).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("Submit failed: resource not found.");
  });
});

describe("platformInputsExist", () => {
  const config = (inputs: [string, string | null][]) => ({
    seekId: "46",
    workflow: { inputs: inputs.map(([category, uuid]) => ({ input: { name: "x", category }, datasetSelectedUuid: uuid })) },
  });
  const listed: Record<string, { uuid: string; name: string }[]> = {
    measurements: [{ uuid: "nifti", name: "converted_dataset" }],
    models: [{ uuid: "skin", name: "model_sds_skin" }],
  };

  it("is true when every dataset the platform assay reads is on the platform", async () => {
    api.useDashboardGetAssayConfigDetails.mockResolvedValue(config([["measurements", "nifti"], ["models", "skin"], ["models", "skin"]]));
    api.useDashboardGetDatasets.mockImplementation(async (category: string) => listed[category] ?? []);
    expect(await platformInputsExist("46")).toBe(true);
    expect(api.useDashboardGetAssayConfigDetails).toHaveBeenCalledWith("46");
    expect(api.useDashboardGetDatasets.mock.calls.map(c => c[0]).sort()).toEqual(["measurements", "models"]);
  });

  it("is false when a dataset is missing, an input has none, or the assay isn't configured", async () => {
    api.useDashboardGetDatasets.mockImplementation(async (category: string) => listed[category] ?? []);
    api.useDashboardGetAssayConfigDetails.mockResolvedValueOnce(config([["measurements", "gone"]]));
    expect(await platformInputsExist("46")).toBe(false);
    api.useDashboardGetAssayConfigDetails.mockResolvedValueOnce(config([["measurements", null]]));
    expect(await platformInputsExist("46")).toBe(false);
    api.useDashboardGetAssayConfigDetails.mockResolvedValueOnce(null);
    expect(await platformInputsExist("46")).toBe(false);
  });

  it("is false when the platform can't be asked, without a toast", async () => {
    api.useDashboardGetAssayConfigDetails.mockRejectedValue({ response: { status: 500 } });
    expect(await platformInputsExist("46")).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });
});
