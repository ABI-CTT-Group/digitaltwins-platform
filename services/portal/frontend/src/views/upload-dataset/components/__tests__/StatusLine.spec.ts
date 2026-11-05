import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import StatusLine from "../StatusLine.vue";

describe("StatusLine", () => {
  it("shows the sentence in its tone, and the hint below it", () => {
    const w = mount(StatusLine, { props: { status: { sentence: "Ready to approve", hint: "Approve it so assays can use it.",
      tone: "needs", group: "needs", problems: [] } } });
    expect(w.find(".status").classes()).toContain("status--needs");
    expect(w.find(".status__sentence").text()).toBe("Ready to approve");
    expect(w.find(".status__detail").text()).toBe("Approve it so assays can use it.");
  });

  it("shows a failure's reason in place of the hint, in full on hover", () => {
    const reason = "npm ERR! missing script: build:plugin";
    const w = mount(StatusLine, { props: { status: { sentence: "Build failed", reason, hint: "ignored",
      tone: "failed", group: "needs", problems: [] } } });
    expect(w.find(".status__detail").text()).toBe(reason);
    expect(w.find(".status__detail").attributes("title")).toBe(reason);
  });

  it("has no second line when there is nothing to add", () => {
    const w = mount(StatusLine, { props: { status: { sentence: "In the platform", tone: "steady", group: "platform", problems: [] } } });
    expect(w.find(".status__detail").exists()).toBe(false);
  });
});
