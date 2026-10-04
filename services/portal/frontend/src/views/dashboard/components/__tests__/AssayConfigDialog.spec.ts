import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";

vi.mock("vue-toastification", () => ({ useToast: () => ({ warning: vi.fn() }) }));
const AssayContentStub = vi.hoisted(() => ({ name: "AssayContent", props: ["assayType", "assayProjectIds", "modelValue"], render: () => null }));
vi.mock("@/components/domain/AssayContent.vue", () => ({ default: AssayContentStub }));

import AssayConfigDialog from "../AssayConfigDialog.vue";

describe("AssayConfigDialog", () => {
  it("hands the assay's type and projects to the form, so it offers matching workflows", () => {
    const w = mount(AssayConfigDialog, {
      props: { modelValue: true, assayName: "Test Assay 2", assayType: "script", assayProjectIds: ["12"] },
      global: { plugins: [testVuetify(), createPinia()] },
    });

    expect(w.findComponent(AssayContentStub).props("assayType")).toBe("script");
    expect(w.findComponent(AssayContentStub).props("assayProjectIds")).toEqual(["12"]);
    w.unmount();
  });
});
