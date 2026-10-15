import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const push = vi.fn();
const check = vi.fn(() => true);
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ isLoggedIn: true }) }));
vi.mock("@/composables/useAuthGuard", () => ({ useAuthGuard: () => ({ check }) }));

import CatalogueDashboardView from "../catalogue-dashboard-view.vue";

const assemblerTile = () =>
  mount(CatalogueDashboardView, { global: { plugins: [testVuetify()] } })
    .findAll("button.tile").find((b) => b.text().includes("Workflow assembler"))!;

describe("catalogue dashboard", () => {
  beforeEach(() => { push.mockClear(); check.mockClear(); });

  it("labels the workflow assembler a prototype and opens it for a signed-in user", async () => {
    const tile = assemblerTile();
    expect(tile.text()).toContain("Prototype");
    expect(tile.text()).not.toContain("Coming soon");
    await tile.trigger("click");
    await flushPromises();
    expect(check).toHaveBeenCalledWith([]);
    expect(push).toHaveBeenCalledWith({ name: "ToolsViewer" });
  });
});
