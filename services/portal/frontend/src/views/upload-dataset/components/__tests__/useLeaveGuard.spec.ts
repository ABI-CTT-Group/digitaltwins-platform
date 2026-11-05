import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import { useLeaveGuard } from "../useLeaveGuard";

const active = ref(false);
const Guarded = defineComponent({ setup() { useLeaveGuard(() => active.value); return () => h("p", "wizard"); } });

async function setup() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/wizard", component: Guarded }, { path: "/hub", component: { render: () => h("p", "hub") } },
  ] });
  await router.push("/wizard");
  const w = mount(RouterView, { global: { plugins: [router] } });
  await flushPromises();
  return { router, w };
}

describe("useLeaveGuard", () => {
  afterEach(() => { active.value = false; vi.restoreAllMocks(); });

  it("lets you leave when there is nothing to lose", async () => {
    const confirm = vi.spyOn(window, "confirm");
    const { router } = await setup();
    await router.push("/hub");
    expect(router.currentRoute.value.path).toBe("/hub");
    expect(confirm).not.toHaveBeenCalled();
  });

  it("asks before leaving, and stays if you say no", async () => {
    active.value = true;
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { router } = await setup();
    await router.push("/hub");
    expect(confirm).toHaveBeenCalledOnce();
    expect(router.currentRoute.value.path).toBe("/wizard");
  });

  it("asks the browser before closing or reloading the tab", async () => {
    active.value = true;
    await setup();
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});
