import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { VBtn } from "vuetify/components";
import { testVuetify } from "../vuetify";

describe("test setup", () => {
  it("mounts a Vuetify component", () => {
    const wrapper = mount(VBtn, { props: { text: "Hello" }, global: { plugins: [testVuetify()] } });
    expect(wrapper.text()).toContain("Hello");
  });
});
