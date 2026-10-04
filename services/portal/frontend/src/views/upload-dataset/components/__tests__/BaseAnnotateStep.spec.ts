import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({
  useWorkflowTools: vi.fn(async () => []), useGetWorkflowToolAnnotation: vi.fn(), useGetToolLocalCwl: vi.fn(), useProbeToolSource: vi.fn(),
}));
vi.mock("@/views/upload-dataset/components/workflow_cwls", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/views/upload-dataset/components/workflow_cwls")>()),
  loadWorkflowCwls: vi.fn(async () => { throw new Error("API rate limit exceeded"); }),
}));

import BaseAnnotateStep from "../BaseAnnotateStep.vue";

describe("BaseAnnotateStep", () => {
  it("says why a workflow's CWL could not be read, before it is known to be an SDS package", async () => {
    const workflow = { id: "w1", sourceType: "github", repositoryUrl: "https://github.com/acme/convert" };
    const w = mount(BaseAnnotateStep, { props: { type: "workflow", data: workflow as any }, global: { plugins: [testVuetify()] } });
    await flushPromises();
    expect(w.text()).toContain("API rate limit exceeded");
  });
});
