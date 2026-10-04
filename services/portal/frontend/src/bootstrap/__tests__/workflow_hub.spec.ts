import { beforeEach, describe, expect, it, vi } from "vitest";

const helpers = vi.hoisted(() => ({ fetchWithLatestBuild: vi.fn(), useCheckName: vi.fn() }));
const platform = vi.hoisted(() => ({ usePlatformWorkflows: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => helpers);
vi.mock("@/bootstrap/platform_api", () => platform);

import { useWorkflowHub } from "@/bootstrap/workflow_api";

beforeEach(() => vi.resetAllMocks());

describe("useWorkflowHub", () => {
  it("lists portal workflows, then platform ones the portal does not know", async () => {
    helpers.fetchWithLatestBuild.mockResolvedValue([
      { id: "p1", name: "portal", uuid: "wf-approved" },
      { id: "p2", name: "draft", uuid: "sparc-workflow-x" },
    ]);
    platform.usePlatformWorkflows.mockResolvedValue([{ id: "wf-1", name: "uploaded", platformOnly: true }]);

    const hub = await useWorkflowHub();

    expect(hub.map((w) => w.id)).toEqual(["p1", "p2", "wf-1"]);
    expect(platform.usePlatformWorkflows).toHaveBeenCalledWith(new Set(["wf-approved", "sparc-workflow-x"]));
  });

  it("still lists portal workflows when the platform is down", async () => {
    helpers.fetchWithLatestBuild.mockResolvedValue([{ id: "p1", name: "portal" }]);
    platform.usePlatformWorkflows.mockRejectedValue(new Error("502"));
    vi.spyOn(console, "warn").mockImplementation(() => {});

    expect((await useWorkflowHub()).map((w) => w.id)).toEqual(["p1"]);
  });
});
