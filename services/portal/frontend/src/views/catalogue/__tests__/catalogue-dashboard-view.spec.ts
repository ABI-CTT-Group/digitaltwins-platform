import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const push = vi.fn();
const check = vi.fn(() => true);
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ isLoggedIn: true }) }));
vi.mock("@/composables/useAuthGuard", () => ({ useAuthGuard: () => ({ check }) }));

import CatalogueDashboardView from "../catalogue-dashboard-view.vue";

const tile = (title: string) =>
  mount(CatalogueDashboardView, { global: { plugins: [testVuetify()] } })
    .findAll("button.tile").find((b) => b.text().includes(title))!;
const assemblerTile = () => tile("Workflow assembler");

describe("catalogue dashboard", () => {
  beforeEach(() => { push.mockClear(); check.mockClear(); });

  it("opens the workflow assembler for a signed-in user", async () => {
    const tile = assemblerTile();
    expect(tile.text()).not.toContain("Coming soon");
    await tile.trigger("click");
    await flushPromises();
    expect(check).toHaveBeenCalledWith([]);
    expect(push).toHaveBeenCalledWith({ name: "ToolsViewer" });
  });

  it("opens the ISA project page for admins only", async () => {
    const isa = tile("ISA project");
    expect(isa.text()).toContain("admin");
    expect(isa.text()).toContain("Open one in the study dashboard");
    await isa.trigger("click");
    await flushPromises();
    expect(check).toHaveBeenCalledWith(["admin"]);
    expect(push).toHaveBeenCalledWith({ name: "IsaProjectPrototype" });
  });

  it("never says prototype", () => {
    const page = mount(CatalogueDashboardView, { global: { plugins: [testVuetify()] } });
    expect(page.text()).not.toMatch(/prototype/i);
  });

  it("has no card for the study dashboard prototype, which is on the home page", () => {
    const tiles = mount(CatalogueDashboardView, { global: { plugins: [testVuetify()] } }).findAll("button.tile");
    expect(tiles.some(t => t.text().includes("Study dashboard"))).toBe(false);
  });
});
