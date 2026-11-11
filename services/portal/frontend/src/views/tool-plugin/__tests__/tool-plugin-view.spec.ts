import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const { http, route } = vi.hoisted(() => ({
  http: { get: vi.fn(), post: vi.fn() },
  route: { query: {} as Record<string, string>, path: "/tool-view" },
}));
vi.mock("@/bootstrap/http", () => ({ default: http, dtApi: {} }));
vi.mock("vue-router", () => ({ useRoute: () => route, useRouter: () => ({ back: vi.fn() }) }));
vi.mock("@/store/remote_store", () => ({
  useRemoteAppStore: () => ({ remoteApp: { path: "/b/my-app.umd.js", expose: "tool_1", name: "t", description: "" } }),
}));
vi.mock("@/bootstrap/dashboard_api", () => ({ useDashboardGetAssayGuiContext: vi.fn() }));
vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: () => "" }));

import { useDashboardGetAssayGuiContext } from "@/bootstrap/dashboard_api";
import ToolPluginView from "../tool-plugin-view.vue";

const mountView = () => mount(ToolPluginView, {
  global: {
    plugins: [testVuetify()],
    stubs: { RemoteComponentApp: { name: "RemoteComponentApp", props: ["src", "expose", "context"], template: "<div class='tool' />" } },
  },
});

// Launched from the Tool Hub: the backend behind /plugin/tool_1 must run before the tool mounts.
describe("tool-plugin-view", () => {
  beforeEach(() => { vi.resetAllMocks(); vi.useFakeTimers(); route.query = {}; });
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

// Launched from a gui assay: the tool gets the launch context, without the portal's own tool record.
describe("tool-plugin-view from an assay", () => {
  beforeEach(() => { vi.resetAllMocks(); route.query = { assay: "12" }; });

  it("hands the tool the launch context", async () => {
    const inputs = [{
      name: "image", datasetUuid: "ds-1", bucket: "measurements", sampleType: "nrrd",
      files: [{ name: "a.nrrd", subjectId: "sub-1", sampleId: "sam-1", key: "ds-1/primary/sub-1/sam-1/a.nrrd",
                url: "/api/dashboard/assays/12/input-files/measurements/ds-1/primary/sub-1/sam-1/a.nrrd" }],
    }];
    vi.mocked(useDashboardGetAssayGuiContext).mockResolvedValue({
      schemaVersion: 1, assayId: "12", cohort: ["sub-1"], inputs,
      tool: { name: "t", path: "/b/annotator.umd.js", expose: "annotator_1" },
    });
    http.post.mockResolvedValue({ state: "running" });
    const view = mountView();
    await flushPromises();
    const context = view.findComponent({ name: "RemoteComponentApp" }).props("context");
    expect(context).toEqual({ schemaVersion: 1, assayId: "12", cohort: ["sub-1"], inputs, getAccessToken: expect.any(Function) });
  });
});
