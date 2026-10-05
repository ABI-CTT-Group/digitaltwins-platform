import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { VSelect } from "vuetify/components";
import { testVuetify } from "@/testing/vuetify";
import type { AssayDetails } from "@/models/types";

const api = vi.hoisted(() => ({
  useDashboardGetDatasets: vi.fn(),
  useDashboardSelectedDatasetSampleTypes: vi.fn(),
  useDashboardWorkflowDetail: vi.fn(),
  useDashboardWorkflows: vi.fn(),
}));
vi.mock("@/bootstrap/dashboard_api", () => api);

import AssayContent from "../AssayContent.vue";

// Dataset categories are plural, matching the dataset table and the CWL `doc` of each port.
const details = (category: string, datasetSelectedUuid = ""): AssayDetails => ({
  seekId: "39",
  uuid: "",
  numberOfParticipants: [],
  isAssayReadyToLaunch: false,
  workflow: {
    uuid: "",
    seekId: "39",
    name: "Workflow - Inference",
    type: "script",
    inputs: [{ input: { name: "mri_nifti", category }, datasetSelectedUuid, sampleSelectedType: "" }],
    outputs: [],
  },
});

let wrapper: ReturnType<typeof mount> | undefined;

async function render(modelValue: AssayDetails, assayType = "script", assayProjectIds = ["12"]) {
  wrapper = mount(AssayContent, {
    props: { modelValue, assayType, assayProjectIds }, global: { plugins: [testVuetify()] },
  });
  await flushPromises();
  return wrapper;
}

const labels = (w: ReturnType<typeof mount>) => w.findAllComponents(VSelect).map((s) => s.props("label"));
const select = (w: ReturnType<typeof mount>, label: string) =>
  w.findAllComponents(VSelect).find((s) => s.props("label") === label)!;

const WORKFLOWS = [
  { uuid: "", seekId: "39", name: "Workflow - Inference", type: "script", projectIds: ["12"] },
  { uuid: "", seekId: "40", name: "Workflow - Data stratification", type: "script", projectIds: ["11", "12"] },
  { uuid: "", seekId: "38", name: "Workflow - Image conversion", type: "script", projectIds: ["11"] },
  { uuid: "", seekId: "91", name: "Workflow - VolView", type: "gui", projectIds: ["12"] },
];

beforeEach(() => {
  vi.resetAllMocks();
  setActivePinia(createPinia());
  api.useDashboardWorkflows.mockResolvedValue(WORKFLOWS);
  api.useDashboardGetDatasets.mockResolvedValue([{ uuid: "ds-1", name: "Breast MRI" }]);
  api.useDashboardSelectedDatasetSampleTypes.mockResolvedValue(["nifti"]);
});
afterEach(() => wrapper?.unmount());

describe("AssayContent: measurements inputs", () => {
  it("asks for a sample type", async () => {
    const w = await render(details("measurements"));

    expect(labels(w)).toContain("Select Sample");
  });

  it("loads the saved dataset's sample types", async () => {
    await render(details("measurements", "ds-1"));

    expect(api.useDashboardSelectedDatasetSampleTypes).toHaveBeenCalledWith("ds-1");
  });

  it("loads sample types when a dataset is picked", async () => {
    const w = await render(details("measurements"));

    select(w, "Select Measurements Dataset").vm.$emit("update:modelValue", "ds-1");
    await flushPromises();

    expect(api.useDashboardSelectedDatasetSampleTypes).toHaveBeenCalledWith("ds-1");
  });
});

describe("AssayContent: models inputs", () => {
  it("does not ask for a sample type", async () => {
    const w = await render(details("models", "ds-2"));

    expect(labels(w)).not.toContain("Select Sample");
    expect(api.useDashboardSelectedDatasetSampleTypes).not.toHaveBeenCalled();
  });
});

describe("AssayContent: workflow", () => {
  it("lists only the workflows of the assay's type in the assay's projects", async () => {
    const w = await render(details("models"), "script", ["12"]);

    expect(select(w, "Select Workflow").props("items")!.map((i: any) => i.seekId)).toEqual(["39", "40"]);
  });

  it("hides workflows that belong only to other projects", async () => {
    const w = await render(details("models"), "script", ["11"]);

    expect(select(w, "Select Workflow").props("items")!.map((i: any) => i.seekId)).toEqual(["40", "38"]);
  });

  it("loads the picked workflow's ports and their datasets", async () => {
    api.useDashboardWorkflowDetail.mockResolvedValue({
      uuid: "", seekId: "40", name: "Workflow - Data stratification",
      inputs: [{ input: { name: "clinical", category: "measurements" }, datasetSelectedUuid: "", sampleSelectedType: "" }],
      outputs: [{ output: { name: "groups", category: "measurements" }, datasetName: "New dataset", sampleName: "groups" }],
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const model = { ...details("models", "ds-2"), numberOfParticipants: [1, 2] };
    const w = await render(model);

    select(w, "Select Workflow").vm.$emit("update:modelValue", "40");
    await flushPromises();

    expect(api.useDashboardWorkflowDetail).toHaveBeenCalledWith("40");
    expect(model.workflow.seekId).toBe("40");
    expect(model.workflow.type).toBe("script");
    expect(model.workflow.inputs!.map((i) => i.input.name)).toEqual(["clinical"]);
    expect(model.workflow.outputs!.map((o) => o.output.name)).toEqual(["groups"]);
    expect(model.numberOfParticipants).toEqual([]);
    expect(api.useDashboardGetDatasets).toHaveBeenLastCalledWith("measurements");
  });

  it("keeps the linked workflow when the reset is not confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const model = details("models", "ds-2");
    const w = await render(model);

    select(w, "Select Workflow").vm.$emit("update:modelValue", "40");
    await flushPromises();

    expect(api.useDashboardWorkflowDetail).not.toHaveBeenCalled();
    expect(model.workflow.seekId).toBe("39");
  });

  it("does not ask before picking the first workflow", async () => {
    api.useDashboardWorkflowDetail.mockResolvedValue({ uuid: "", seekId: "40", name: "W", inputs: [], outputs: [] });
    const confirm = vi.spyOn(window, "confirm");
    const model = { ...details("models"), workflow: { uuid: "", seekId: "", name: "", type: "script", inputs: [], outputs: [] } };
    const w = await render(model);

    select(w, "Select Workflow").vm.$emit("update:modelValue", "40");
    await flushPromises();

    expect(confirm).not.toHaveBeenCalled();
    expect(model.workflow.seekId).toBe("40");
  });

  it("fetches the workflow list once per page load", async () => {
    await render(details("models"));
    wrapper!.unmount();
    await render(details("models"));

    expect(api.useDashboardWorkflows).toHaveBeenCalledTimes(1);
  });
});
