import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import HubFilterChips from "../HubFilterChips.vue";

const counts = { all: 6, needs: 3, progress: 0, platform: 2 };

describe("HubFilterChips", () => {
  it("lists the four filters, counting only what needs you", () => {
    const w = mount(HubFilterChips, { props: { modelValue: "all", counts } });
    expect(w.findAll("button").map((b) => b.text())).toEqual(["All", "Needs you 3", "In progress", "In the platform"]);
    expect(w.find("button[aria-pressed='true']").text()).toBe("All");
  });

  it("picks a filter", async () => {
    const w = mount(HubFilterChips, { props: { modelValue: "all", counts } });
    await w.findAll("button")[1].trigger("click");
    expect(w.emitted("update:modelValue")?.[0]).toEqual(["needs"]);
  });

  it("drops the count when nothing needs you", () => {
    const w = mount(HubFilterChips, { props: { modelValue: "needs", counts: { ...counts, needs: 0 } } });
    expect(w.findAll("button")[1].text()).toBe("Needs you");
  });
});
