import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useWorkflowHub: vi.fn(), useMeasurement: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({}));
vi.mock("@/bootstrap/platform_api", () => ({}));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowHub: api.useWorkflowHub }));
vi.mock("@/bootstrap/measurement_api", () => ({ useMeasurement: api.useMeasurement }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn() }) }));

import WorkflowsOverallView from "../../workflow/WorkflowsOverallView.vue";
import WorkflowCard from "../WorkflowCard.vue";
import MeasurementsOverallView from "../../measurements/MeasurementsOverallView.vue";
import MeasurementCard from "../../measurements/components/MeasurementCard.vue";

const plugins = [testVuetify()];

const workflow = (id: string, extra: object = {}) =>
  ({ id, name: id, version: "1", repositoryUrl: "", status: "completed", createdAt: "", updatedAt: "", ...extra });
const WORKFLOWS = [
  workflow("draft"),
  workflow("legacy-approved", { uuid: "sparc-workflow-$x" }),
  workflow("approved", { uuid: "a8d6da0e-1" }),
  workflow("uploaded", { uuid: "b1", platformOnly: true }),
];

const measurement = (id: string, status: string, uuid?: string) =>
  ({ id, name: id, status, uuid, createdAt: "", updatedAt: "" });
const MEASUREMENTS = [
  measurement("upload:staged", "pending"),
  measurement("upload:failed", "submit_failed"),
  measurement("dataset:done", "completed", "d1"),
  measurement("dataset:fhir-failed", "fhir_failed", "d2"),
  measurement("dataset:fhir-pushing", "uploading", "d3"),
];

/** Mount a hub, pick each filter option, and collect the names it lists. */
async function listed(view: any, card: any, prop: string) {
  const w = mount(view, { global: { plugins } });
  await flushPromises();
  const names = () => w.findAllComponents(card).map((c) => (c.props(prop) as { name: string }).name);
  const result: Record<string, string[]> = { all: names() };
  for (const value of ["in-platform", "not-in-platform"]) {
    w.findComponent({ name: "VSelect" }).vm.$emit("update:modelValue", value);
    await flushPromises();
    result[value] = names();
  }
  w.unmount();
  return result;
}

describe("Workflow Hub registration filter", () => {
  it("splits workflows by whether they reached the platform", async () => {
    api.useWorkflowHub.mockResolvedValue(WORKFLOWS);

    expect(await listed(WorkflowsOverallView, WorkflowCard, "workflow")).toEqual({
      all: ["draft", "legacy-approved", "approved", "uploaded"],
      "in-platform": ["approved", "uploaded"],
      "not-in-platform": ["draft", "legacy-approved"],
    });
  });
});

describe("Measurements registration filter", () => {
  it("counts every committed dataset as in platform, whatever its FHIR state", async () => {
    api.useMeasurement.mockResolvedValue(MEASUREMENTS);

    expect(await listed(MeasurementsOverallView, MeasurementCard, "measurement")).toEqual({
      all: MEASUREMENTS.map((m) => m.name),
      "in-platform": ["dataset:done", "dataset:fhir-failed", "dataset:fhir-pushing"],
      "not-in-platform": ["upload:staged", "upload:failed"],
    });
  });
});

describe("MeasurementCard", () => {
  it("tags a committed dataset as in platform, next to its FHIR status", () => {
    const tagged = (m: object) =>
      mount(MeasurementCard, { props: { measurement: m as any }, global: { plugins } }).text();

    expect(tagged(measurement("dataset:done", "completed", "d1"))).toContain("in platform");
    const fhirFailed = tagged(measurement("dataset:fhir-failed", "fhir_failed", "d2"));
    expect(fhirFailed).toContain("in platform");
    expect(fhirFailed).toContain("FHIR failed");
    expect(tagged(measurement("upload:staged", "pending"))).not.toContain("in platform");
  });
});
