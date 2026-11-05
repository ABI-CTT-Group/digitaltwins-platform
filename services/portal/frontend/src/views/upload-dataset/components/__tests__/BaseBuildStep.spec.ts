import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import BaseBuildStep from "../BaseBuildStep.vue";

const button = (w: ReturnType<typeof mount>, label: string) => w.findAll("button").find((b) => b.text() === label)!;

describe("BaseBuildStep", () => {
  it("starts the build", async () => {
    const submit = vi.fn(async () => {});
    const w = mount(BaseBuildStep, { props: { type: "tool", data: { id: "t1", name: "curator" } as any, submit },
      global: { plugins: [testVuetify()] } });
    await button(w, "Build").trigger("click");
    await flushPromises();
    expect(submit).toHaveBeenCalledWith("t1");
  });

  it("shows why the build couldn't start, and lets you try again", async () => {
    const submit = vi.fn().mockRejectedValueOnce({ response: { status: 400, data: { detail: "Repository not found" } } });
    const w = mount(BaseBuildStep, { props: { type: "workflow", data: { id: "w1", name: "seg" } as any, submit },
      global: { plugins: [testVuetify()] } });
    await button(w, "Build").trigger("click");
    await flushPromises();
    expect(w.text()).toContain("Starting the build failed: Repository not found");
    expect(button(w, "Build").attributes("disabled")).toBeUndefined();
  });
});
