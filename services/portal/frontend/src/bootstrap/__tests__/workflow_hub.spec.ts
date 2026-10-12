import { beforeEach, describe, expect, it, vi } from "vitest";

const helpers = vi.hoisted(() => ({ fetchWithLatestBuild: vi.fn(), useCheckName: vi.fn() }));
const platform = vi.hoisted(() => ({ withPlatformWorkflows: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => helpers);
vi.mock("@/bootstrap/platform_api", () => platform);

import { useWorkflowHub } from "@/bootstrap/workflow_api";

beforeEach(() => vi.resetAllMocks());

describe("useWorkflowHub", () => {
  it("lists portal workflows with what the platform knows of them", async () => {
    const portal = [{ id: "p1", name: "portal", uuid: "wf-approved" }, { id: "p2", name: "draft", uuid: "sparc-workflow-x" }];
    helpers.fetchWithLatestBuild.mockResolvedValue(portal);
    platform.withPlatformWorkflows.mockResolvedValue([...portal, { id: "wf-1", name: "uploaded", platformOnly: true }]);

    const hub = await useWorkflowHub();

    expect(hub.map((w) => w.id)).toEqual(["p1", "p2", "wf-1"]);
    expect(platform.withPlatformWorkflows).toHaveBeenCalledWith(portal);
  });

  it("still lists portal workflows when the platform is down", async () => {
    helpers.fetchWithLatestBuild.mockResolvedValue([{ id: "p1", name: "portal" }]);
    platform.withPlatformWorkflows.mockRejectedValue(new Error("502"));
    vi.spyOn(console, "warn").mockImplementation(() => {});

    expect((await useWorkflowHub()).map((w) => w.id)).toEqual(["p1"]);
  });

  it("keeps the latest build's handoff error", async () => {
    helpers.fetchWithLatestBuild.mockResolvedValue([]);
    platform.withPlatformWorkflows.mockResolvedValue([]);
    await useWorkflowHub();

    const enrich = helpers.fetchWithLatestBuild.mock.calls[0][2];
    expect(await enrich({}, { handoffStatus: "failed", handoffError: "SEEK 403" }))
      .toEqual({ handoffStatus: "failed", handoffError: "SEEK 403" });
  });
});
