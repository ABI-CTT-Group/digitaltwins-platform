import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useModelFhirDraft: vi.fn(), useUpsertModelAnnotation: vi.fn() }));
vi.mock("@/bootstrap/model_api", () => api);

import ModelFhirStep from "../steps/ModelFhirStep.vue";

const MODEL = { id: "upload:u1", name: "Skin", status: "pending", createdAt: "", updatedAt: "" };
let wrapper: ReturnType<typeof mount>;

async function render() {
  wrapper = mount(ModelFhirStep, { props: { model: MODEL }, global: { plugins: [testVuetify()] } });
  await flushPromises();
}

beforeEach(() => {
  vi.resetAllMocks();
  api.useModelFhirDraft.mockResolvedValue({ description: "From upload", version: "" });
  api.useUpsertModelAnnotation.mockResolvedValue(undefined);
});
afterEach(() => wrapper?.unmount());

describe("ModelFhirStep", () => {
  it("finishes without an annotation when FHIR is off", async () => {
    await render();

    expect(wrapper.find('[data-testid="model-version"]').exists()).toBe(false);
    await wrapper.find('[data-testid="finish"]').trigger("click");
    await flushPromises();

    expect(api.useUpsertModelAnnotation).not.toHaveBeenCalled();
    expect(wrapper.emitted("finished")).toHaveLength(1);
  });

  it("stores the Device fields when FHIR is on", async () => {
    await render();
    await wrapper.find('[data-testid="publish-fhir"] input').setValue(true);
    await flushPromises();

    expect((wrapper.find('[data-testid="model-description"] textarea').element as HTMLTextAreaElement).value)
      .toBe("From upload");
    await wrapper.find('[data-testid="model-version"] input').setValue("2.1");
    await wrapper.find('[data-testid="finish"]').trigger("click");
    await flushPromises();

    expect(api.useUpsertModelAnnotation).toHaveBeenCalledWith("upload:u1", { description: "From upload", version: "2.1" });
    expect(wrapper.emitted("finished")).toHaveLength(1);
  });

  it("shows the server's error and stays open when saving fails", async () => {
    api.useUpsertModelAnnotation.mockRejectedValue({ response: { data: { detail: "model.version must be a string" } } });
    await render();
    await wrapper.find('[data-testid="publish-fhir"] input').setValue(true);
    await flushPromises();

    await wrapper.find('[data-testid="finish"]').trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("model.version must be a string");
    expect(wrapper.emitted("finished")).toBeUndefined();
  });
});
