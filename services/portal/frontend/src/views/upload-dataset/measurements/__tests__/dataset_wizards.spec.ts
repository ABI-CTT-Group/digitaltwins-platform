import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import { testVuetify } from "@/testing/vuetify";

const api = vi.hoisted(() => ({ useGetMeasurement: vi.fn(), useMeasurementRetryFhir: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/measurement_api", () => api);
vi.mock("vue-toastification", () => ({ useToast: () => ({ error: vi.fn(), success: vi.fn() }) }));

import UploadMeasurementForm from "../UploadMeasurementForm.vue";
import UploadModelForm from "../../models/UploadModelForm.vue";

const CREATED = { id: "upload:m1", name: "scans", status: "pending", createdAt: "", updatedAt: "" };
const stubs = {
  InformationStep: defineComponent({
    props: ["resumeMeasurementId", "category"],
    emits: ["created", "cancel"],
    setup(props, { emit }) {
      return () => h("button", { class: "info-upload", "data-resume": props.resumeMeasurementId ?? "",
        onClick: () => emit("created", CREATED) }, "upload");
    },
  }),
  AnnotationStep: defineComponent({
    props: ["measurement"], emits: ["saved", "skip", "cancel"],
    setup(props, { emit }) {
      return () => h("div", { class: "annotate", "data-id": props.measurement.id },
        [h("button", { class: "annotate-skip", onClick: () => emit("skip") }, "skip")]);
    },
  }),
  ModelFhirStep: defineComponent({
    props: ["model"], emits: ["finished", "cancel"],
    setup(props, { emit }) {
      return () => h("button", { class: "fhir-finish", "data-id": props.model.id, onClick: () => emit("finished", false) }, "done");
    },
  }),
};

async function setup(base: string, form: any, names: [string, string, string], path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{
    path: base, component: RouterView, children: [
      { path: "", name: names[0], component: { render: () => h("p", { class: "hub" }, "hub") } },
      { path: "new", name: names[1], component: form },
      { path: ":id/register", name: names[2], component: form, props: true },
    ],
  }] });
  await router.push(path);
  const w = mount(RouterView, { global: { plugins: [router, testVuetify()], stubs } });
  await flushPromises();
  return { router, w };
}
const measurements = (path: string) => setup("/catalogue/measurements", UploadMeasurementForm,
  ["UploadMeasurementsDataset", "RegisterMeasurement", "ContinueMeasurementRegistration"], path);
const models = (path: string) => setup("/catalogue/models", UploadModelForm,
  ["UploadModelDataset", "RegisterModel", "ContinueModelRegistration"], path);

describe("measurement wizard", () => {
  afterEach(() => vi.resetAllMocks());

  it("moves to the dataset's own URL once its upload is staged", async () => {
    const { router, w } = await measurements("/catalogue/measurements/new");
    await w.find(".info-upload").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("ContinueMeasurementRegistration");
    expect(router.currentRoute.value.params.id).toBe("upload:m1");
    expect(router.currentRoute.value.query.step).toBe("annotation");
    expect(w.find(".annotate").attributes("data-id")).toBe("upload:m1");
  });

  it("resumes a paused upload", async () => {
    const { w } = await measurements("/catalogue/measurements/upload:m1/register?step=upload");
    expect(w.find(".info-upload").attributes("data-resume")).toBe("upload:m1");
  });

  it("opens a staged dataset's annotation, which you can skip", async () => {
    api.useGetMeasurement.mockResolvedValue(CREATED);
    const { router, w } = await measurements("/catalogue/measurements/upload:m1/register?step=annotation");
    expect(api.useGetMeasurement).toHaveBeenCalledWith("upload:m1");
    await w.find(".annotate-skip").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("UploadMeasurementsDataset");
  });
});

describe("model wizard", () => {
  afterEach(() => vi.resetAllMocks());

  it("moves to the model's own URL once its upload is staged, then back to the hub", async () => {
    const { router, w } = await models("/catalogue/models/new");
    await w.find(".info-upload").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("ContinueModelRegistration");
    await w.find(".fhir-finish").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("UploadModelDataset");
  });
});
