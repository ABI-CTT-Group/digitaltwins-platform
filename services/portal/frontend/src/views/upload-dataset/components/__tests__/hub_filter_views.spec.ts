import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useWorkflowHub: vi.fn(), useMeasurement: vi.fn(), useModels: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({ useRetryToolFhir: vi.fn() }));
vi.mock("@/bootstrap/platform_api", () => ({}));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ hasAdminRole: false }) }));
vi.mock("@/bootstrap/workflow_api", () => ({ useWorkflowHub: api.useWorkflowHub }));
vi.mock("@/bootstrap/measurement_api", () => ({ useMeasurement: api.useMeasurement }));
vi.mock("@/bootstrap/model_api", () => ({ useModels: api.useModels }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), warning: vi.fn(), success: vi.fn() }) }));

import WorkflowsOverallView from "../../workflow/WorkflowsOverallView.vue";
import WorkflowCard from "../WorkflowCard.vue";
import MeasurementsOverallView from "../../measurements/MeasurementsOverallView.vue";
import MeasurementCard from "../../measurements/components/MeasurementCard.vue";
import ModelsOverallView from "../../models/ModelsOverallView.vue";
import ModelCard from "../../models/components/ModelCard.vue";

const plugins = [testVuetify()];

const workflow = (id: string, extra: object = {}) =>
  ({ id, name: id, version: "1", repositoryUrl: "", status: "completed", latestBuildId: "b1", workflowType: "script",
    isSds: true, createdAt: "", updatedAt: "", ...extra });
const WORKFLOWS = [
  workflow("approved", { uuid: "a8d6da0e-1", handoffStatus: "completed" }),
  workflow("building", { status: "building" }),
  workflow("built"),
  workflow("uploaded", { uuid: "b1", platformOnly: true, latestBuildId: undefined }),
  workflow("legacy", { isSds: false }),
  workflow("approval-failed", { handoffStatus: "failed" }),
];

const measurement = (id: string, status: string, uuid?: string) =>
  ({ id, name: id, status, uuid, createdAt: "", updatedAt: "" });
const MEASUREMENTS = [
  measurement("dataset:done", "completed", "d1"),
  measurement("upload:staged", "pending"),
  measurement("upload:approving", "uploading"),
  measurement("dataset:fhir-failed", "fhir_failed", "d2"),
  measurement("upload:paused", "pending_upload"),
];

/** Mount a hub, pick each filter chip, and collect the names it lists and the chips' text. */
async function listed(view: any, card: any, prop: string) {
  const w = mount(view, { global: { plugins } });
  await flushPromises();
  const names = () => w.findAllComponents(card).map((c) => (c.props(prop) as { name: string }).name);
  const chips = w.findAll(".hub-filter__chip");
  const result: Record<string, string[]> = { chips: chips.map((c) => c.text()) };
  for (const chip of chips) {
    await chip.trigger("click");
    await flushPromises();
    result[chip.text()] = names();
  }
  w.unmount();
  return result;
}

// Each hub lists what needs you first, and filters by the card's status group.
describe("Workflow Hub filter", () => {
  it("groups workflows by what they need", async () => {
    api.useWorkflowHub.mockResolvedValue(WORKFLOWS);

    expect(await listed(WorkflowsOverallView, WorkflowCard, "workflow")).toEqual({
      chips: ["All", "Needs you 2", "In progress", "In the platform"],
      All: ["built", "approval-failed", "approved", "building", "uploaded", "legacy"],
      "Needs you 2": ["built", "approval-failed"],
      "In progress": ["building"],
      "In the platform": ["approved", "uploaded"],
    });
  });
});

describe("Measurements and Models filter", () => {
  const expected = {
    chips: ["All", "Needs you 3", "In progress", "In the platform"],
    All: ["upload:staged", "dataset:fhir-failed", "upload:paused", "dataset:done", "upload:approving"],
    "Needs you 3": ["upload:staged", "dataset:fhir-failed", "upload:paused"],
    "In progress": ["upload:approving"],
    "In the platform": ["dataset:done"],
  };

  it("groups measurements, a failed FHIR push needing you", async () => {
    api.useMeasurement.mockResolvedValue(MEASUREMENTS);
    expect(await listed(MeasurementsOverallView, MeasurementCard, "measurement")).toEqual(expected);
  });

  it("groups models the same way", async () => {
    api.useModels.mockResolvedValue(MEASUREMENTS);
    expect(await listed(ModelsOverallView, ModelCard, "model")).toEqual(expected);
  });
});
