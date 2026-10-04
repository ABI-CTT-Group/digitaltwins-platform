import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { VSelect } from "vuetify/components";
import { testVuetify } from "@/testing/vuetify";
import type { AssayDetails } from "@/models/types";

const api = vi.hoisted(() => ({
  useDashboardGetDatasets: vi.fn(),
  useDashboardSelectedDatasetSampleTypes: vi.fn(),
  useDashboardWorkflowDetail: vi.fn(),
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

async function render(modelValue: AssayDetails) {
  wrapper = mount(AssayContent, { props: { modelValue }, global: { plugins: [testVuetify()] } });
  await flushPromises();
  return wrapper;
}

const labels = (w: ReturnType<typeof mount>) => w.findAllComponents(VSelect).map((s) => s.props("label"));

beforeEach(() => {
  vi.resetAllMocks();
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

    w.findAllComponents(VSelect)[0].vm.$emit("update:modelValue", "ds-1");
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
