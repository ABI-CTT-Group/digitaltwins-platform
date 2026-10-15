import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

import CommonInfoForm from "../CommonInfoForm.vue";

const mountForm = (props: Record<string, unknown> = {}) =>
  mount(CommonInfoForm, { props: { nameErr: null, cwlRepoErr: null, ...props }, global: { plugins: [testVuetify()] } });
const sourceGroup = (w: ReturnType<typeof mountForm>) => w.findAllComponents({ name: "VRadioGroup" })[0];

describe("CommonInfoForm", () => {
  it("offers Local Folder first and selects it by default", () => {
    const w = mountForm();
    expect(sourceGroup(w).findAllComponents({ name: "VRadio" }).map((r) => r.props("label")))
      .toEqual(["Local Folder", "Git URL"]);
    expect(sourceGroup(w).props("modelValue")).toBe("local");
  });
});
