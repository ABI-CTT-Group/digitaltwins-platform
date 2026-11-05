import { afterEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

import RegistryView from "../RegistryView.vue";

type Row = { id: string; name: string; status?: string };
const rows: Row[] = [{ id: "a", name: "alpha" }, { id: "b", name: "beta" }];

const mountView = (props: Record<string, unknown>) => mount(RegistryView as any, {
  props: { registerLabel: "Register a tool", ...props },
  slots: {
    default: `<template #default="{ items }"><div v-for="i in items" :key="i.id" class="row">{{ i.name }}</div></template>`,
    empty: "<p class='empty'>No tools yet.</p>",
  },
  global: { plugins: [testVuetify()] },
});
const buttons = (w: ReturnType<typeof mount>, label: string) => w.findAll("button").filter((b) => b.text().includes(label));

// The hubs' list: what it shows while loading, when loading fails, when it's empty, and when a poll fails.
describe("RegistryView", () => {
  afterEach(() => vi.useRealTimers());

  it("shows a loading state, not the empty state, until the list arrives", async () => {
    let resolve!: (r: Row[]) => void;
    const view = mountView({ fetchList: () => new Promise<Row[]>((r) => { resolve = r; }) });
    await flushPromises();
    expect(view.text()).toContain("Loading");
    expect(view.find(".empty").exists()).toBe(false);
    resolve(rows);
    await flushPromises();
    expect(view.findAll(".row").map((r) => r.text())).toEqual(["alpha", "beta"]);
  });

  it("explains a failed load and retries it", async () => {
    const fetchList = vi.fn().mockRejectedValueOnce({ response: { status: 502 } }).mockResolvedValueOnce(rows);
    const view = mountView({ fetchList });
    await flushPromises();
    expect(view.text()).toContain("Couldn't load the list");
    expect(view.find(".empty").exists()).toBe(false);
    await buttons(view, "Try again")[0].trigger("click");
    await flushPromises();
    expect(fetchList).toHaveBeenCalledTimes(2);
    expect(view.findAll(".row")).toHaveLength(2);
  });

  it("shows the hub's empty state for an empty list", async () => {
    const view = mountView({ fetchList: async () => [] });
    await flushPromises();
    expect(view.find(".empty").text()).toBe("No tools yet.");
  });

  it("orders the list with the hub's sort, before searching", async () => {
    const view = mountView({ fetchList: async () => rows, sortFn: (x: Row, y: Row) => y.name.localeCompare(x.name) });
    await flushPromises();
    expect(view.findAll(".row").map((r) => r.text())).toEqual(["beta", "alpha"]);
  });

  it("says nothing matches when a filter hides every item", async () => {
    const view = mountView({ fetchList: async () => rows, filterFn: () => false });
    await flushPromises();
    expect(view.text()).toContain("Nothing matches");
    expect(view.find(".empty").exists()).toBe(false);
  });

  it("keeps the last list when a poll fails, and says so", async () => {
    vi.useFakeTimers();
    const pending = [{ ...rows[0], status: "building" }];
    const fetchList = vi.fn().mockResolvedValueOnce(pending).mockRejectedValue(new Error("offline"));
    const view = mountView({ fetchList, pollInterval: 1000, isPending: (items: Row[]) => items.some((i) => i.status === "building") });
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();
    expect(view.findAll(".row")).toHaveLength(1);
    expect(view.text()).toContain("Couldn't refresh");
  });

  it("emits register from its one register button", async () => {
    const view = mountView({ fetchList: async () => rows });
    await flushPromises();
    await buttons(view, "Register a tool")[0].trigger("click");
    expect(view.emitted("register")).toHaveLength(1);
  });
});
