import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(), fetchWithLatestBuild: vi.fn() }));
vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: () => "tok", getKeycloak: vi.fn() }));

import { getLogs } from "@/bootstrap/tool_api";

afterEach(() => vi.unstubAllGlobals());

// Build/deploy logs bypass axios (plain fetch for streaming), so they spell out the builder's prefix.
describe("tool logs", () => {
  it.each([
    ["build", "/api/portal/tools/builds/b1/logs"],
    ["deploy", "/api/portal/tools/deploy/b1/logs"],
  ] as const)("fetches %s logs from the builder", async (kind, url) => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve("log") });
    vi.stubGlobal("fetch", fetch);
    expect(await getLogs(kind, "b1")).toBe("log");
    expect(fetch).toHaveBeenCalledWith(url, { headers: { Authorization: "Bearer tok" } });
  });
});
