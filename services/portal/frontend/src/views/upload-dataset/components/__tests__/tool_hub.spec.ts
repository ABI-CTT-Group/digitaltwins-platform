import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, dtGet, fetchWithLatestBuild } = vi.hoisted(() => ({
  get: vi.fn(), dtGet: vi.fn(), fetchWithLatestBuild: vi.fn(),
}));
vi.mock("@/bootstrap/http", () => ({ default: { get }, dtApi: { get: dtGet } }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(), fetchWithLatestBuild }));
vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: vi.fn(), getKeycloak: vi.fn() }));

import { useToolHub } from "@/bootstrap/tool_api";

const kindOf = (t: any) => t.kind ?? (t.platformOnly ? "platform" : "portal");

describe("useToolHub", () => {
  beforeEach(() => {
    fetchWithLatestBuild.mockResolvedValue([{ id: "t1", uuid: "tool-a", name: "portal tool" }]);
    dtGet.mockResolvedValue({ datasets: [
      { datasetUuid: "tool-v", datasetName: "tool_volview", toolType: "gui" },
      { datasetUuid: "tool-x", datasetName: "tool_other", toolType: "script", fhirStatus: "completed" },
      { datasetUuid: "tool-a", datasetName: "portal tool", toolType: "gui", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" },
    ] });
  });

  it("lists a gui workflow's tool once, instead of its platform dataset", async () => {
    get.mockResolvedValue([{ id: "w1", kind: "workflow", uuid: "tool-v", name: "tool_volview" }]);

    const hub = await useToolHub();

    expect(get).toHaveBeenCalledWith("/workflow/gui-tools");
    expect(hub.map((t) => [t.name, kindOf(t)])).toEqual([
      ["portal tool", "portal"], ["tool_volview", "workflow"], ["tool_other", "platform"],
    ]);
  });

  it("still lists the other tools when the workflow tools can't be fetched", async () => {
    get.mockRejectedValue(new Error("502"));

    const hub = await useToolHub();

    expect(hub.map((t) => t.name)).toEqual(["portal tool", "tool_volview", "tool_other"]);
  });

  it("gives each tool its platform dataset's FHIR status", async () => {
    get.mockResolvedValue([{ id: "w1", kind: "workflow", uuid: "tool-v", name: "tool_volview" }]);

    const [portal, workflowTool, platform] = await useToolHub();

    expect(portal).toMatchObject({ id: "t1", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" });
    expect(workflowTool.fhirStatus).toBeUndefined();
    expect(platform).toMatchObject({ name: "tool_other", fhirStatus: "completed" });
  });

  it("still lists the portal's tools when the platform can't be reached", async () => {
    get.mockResolvedValue([]);
    dtGet.mockRejectedValue(new Error("502"));

    expect((await useToolHub()).map((t) => t.name)).toEqual(["portal tool"]);
  });

  it("keeps the latest build's handoff error", async () => {
    get.mockResolvedValue([]);
    await useToolHub();

    const enrich = fetchWithLatestBuild.mock.calls[0][2];
    expect(await enrich({ id: "t1" }, { handoffStatus: "failed", handoffError: "SEEK 403", status: "completed" }))
      .toEqual({ handoffStatus: "failed", handoffError: "SEEK 403" });
  });
});
