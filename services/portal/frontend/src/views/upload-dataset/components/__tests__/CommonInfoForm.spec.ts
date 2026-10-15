import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

import CommonInfoForm from "../CommonInfoForm.vue";

const mountForm = (props: Record<string, unknown> = {}) =>
  mount(CommonInfoForm, { props: { nameErr: null, cwlRepoErr: null, ...props }, global: { plugins: [testVuetify()] } });
const nameField = (w: ReturnType<typeof mountForm>) =>
  w.findAllComponents({ name: "VTextField" }).find((f) => /^My \w+ Name$/.test(f.props("label")))!;
const sourceGroup = (w: ReturnType<typeof mountForm>) => w.findAllComponents({ name: "VRadioGroup" })[0];

describe("CommonInfoForm", () => {
  it("offers Local Folder first and selects it by default", () => {
    const w = mountForm();
    expect(sourceGroup(w).findAllComponents({ name: "VRadio" }).map((r) => r.props("label")))
      .toEqual(["Local Folder", "Git URL"]);
    expect(sourceGroup(w).props("modelValue")).toBe("local");
  });

  it("asks a tool for its tool name", () => {
    const w = mountForm({ type: "tool" });
    expect(w.text()).toContain("Tool Name *");
    expect(w.text()).not.toContain("Workflow Name *");
    expect(nameField(w).props("label")).toBe("My Tool Name");
  });

  it("asks a workflow for its workflow name", () => {
    const w = mountForm({ type: "workflow" });
    expect(w.text()).toContain("Workflow Name *");
    expect(nameField(w).props("label")).toBe("My Workflow Name");
  });
});
