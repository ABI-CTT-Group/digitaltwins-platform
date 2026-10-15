import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import AssayActionBar from "../AssayActionBar.vue";

const mountBar = (props: Record<string, unknown>) =>
  mount(AssayActionBar, { props, global: { plugins: [testVuetify()] } });

const verifyButton = (wrapper: ReturnType<typeof mountBar>) =>
  wrapper.findAll("button").find((b) => b.text() === "Verify")!;

describe("AssayActionBar Verify", () => {
  it("is enabled for a ready notebook assay and emits verify", async () => {
    const wrapper = mountBar({ ready: true, isNotebook: true });

    expect(verifyButton(wrapper).attributes("disabled")).toBeUndefined();
    await verifyButton(wrapper).trigger("click");
    expect(wrapper.emitted("verify")).toHaveLength(1);
  });

  it("is disabled for a notebook assay that is not ready", () => {
    expect(verifyButton(mountBar({ ready: false, isNotebook: true })).attributes("disabled")).toBeDefined();
  });

  it("is disabled for script and gui assays", () => {
    expect(verifyButton(mountBar({ ready: true, isNotebook: false, isScript: true })).attributes("disabled")).toBeDefined();
  });
});
