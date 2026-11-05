import { beforeEach, describe, expect, it, vi } from "vitest";

const { http } = vi.hoisted(() => ({ http: { get: vi.fn(), post: vi.fn() } }));
vi.mock("@/bootstrap/http", () => ({ default: http, dtApi: {} }));

import { BackendStartError, ensureBackend } from "@/bootstrap/tool_api";

beforeEach(() => vi.resetAllMocks());

// Launch starts a GUI tool's backend in /tool-view before the tool mounts.
describe("ensureBackend", () => {
  it("resolves at once when the tool has no backend or it is running", async () => {
    for (const state of ["none", "running"]) {
      http.post.mockResolvedValueOnce({ state });
      await ensureBackend("tool_1", undefined, 0);
    }
    expect(http.post.mock.calls).toEqual([["/tools/backend/tool_1/start"], ["/tools/backend/tool_1/start"]]);
    expect(http.get).not.toHaveBeenCalled();
  });

  it("waits until a start or a deploy has finished, reporting each state", async () => {
    http.post.mockResolvedValue({ state: "starting" });
    http.get.mockResolvedValueOnce({ state: "deploying" }).mockResolvedValueOnce({ state: "running" });
    const states: string[] = [];
    await ensureBackend("tool_1", (s) => states.push(s), 0);
    expect(states).toEqual(["starting", "deploying"]);
    expect(http.get).toHaveBeenCalledWith("/tools/backend/tool_1");
  });

  it("rejects with the deploy error when the backend failed", async () => {
    http.post.mockResolvedValue({ state: "deploying" });
    http.get.mockResolvedValue({ state: "failed", error: "image build failed" });
    await expect(ensureBackend("tool_1", undefined, 0)).rejects.toEqual(new BackendStartError("image build failed"));
  });
});
