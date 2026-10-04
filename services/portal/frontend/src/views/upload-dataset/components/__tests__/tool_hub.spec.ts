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
      { datasetUuid: "tool-x", datasetName: "tool_other", toolType: "script" },
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
});
