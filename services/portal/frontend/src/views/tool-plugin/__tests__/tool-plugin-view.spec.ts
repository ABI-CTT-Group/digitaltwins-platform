import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const { http } = vi.hoisted(() => ({ http: { get: vi.fn(), post: vi.fn() } }));
vi.mock("@/bootstrap/http", () => ({ default: http, dtApi: {} }));
vi.mock("vue-router", () => ({ useRoute: () => ({ query: {}, path: "/tool-view" }), useRouter: () => ({ back: vi.fn() }) }));
vi.mock("@/store/remote_store", () => ({
  useRemoteAppStore: () => ({ remoteApp: { path: "/b/my-app.umd.js", expose: "tool_1", name: "t", description: "" } }),
}));
vi.mock("@/bootstrap/dashboard_api", () => ({ useDashboardGetAssayGuiContext: vi.fn() }));
vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: () => "" }));

import ToolPluginView from "../tool-plugin-view.vue";

const mountView = () => mount(ToolPluginView, {
  global: { plugins: [testVuetify()], stubs: { RemoteComponentApp: { template: "<div class='tool' />" } } },
});

// Launched from the Tool Hub: the backend behind /plugin/tool_1 must run before the tool mounts.
describe("tool-plugin-view", () => {
  beforeEach(() => { vi.resetAllMocks(); vi.useFakeTimers(); });
  afterEach(() => vi.useRealTimers());

  it("mounts the tool only once its backend is running", async () => {
    http.post.mockResolvedValue({ state: "deploying" });
    http.get.mockResolvedValue({ state: "running" });
    const view = mountView();
    await flushPromises();
    expect(http.post).toHaveBeenCalledWith("/tools/backend/tool_1/start");
    expect(view.find(".tool").exists()).toBe(false);
    expect(view.text()).toContain("Deploying the tool's backend");
    await vi.advanceTimersByTimeAsync(2000);
    await flushPromises();
    expect(view.find(".tool").exists()).toBe(true);
  });

  it("shows why the backend did not start", async () => {
    http.post.mockResolvedValue({ state: "failed", error: "image build failed" });
    const view = mountView();
    await flushPromises();
    expect(view.find(".tool").exists()).toBe(false);
    expect(view.text()).toContain("Launch failed: image build failed");
  });
});
