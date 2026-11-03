import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: vi.fn(), getKeycloak: vi.fn() }));

import axios, { AxiosError, CanceledError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { dtApiAxios } from "@/bootstrap/http";
import { getAccessToken, getKeycloak } from "@/bootstrap/keycloak";

// The gateway sends /api/builder/ to the builder and the rest of /api/ to the platform API.
describe("http base URLs", () => {
  it("sends the default client to the builder", () => {
    expect(axios.defaults.baseURL).toBe("/api/builder");
  });

  it("sends dtApi to the platform API", () => {
    expect(dtApiAxios.defaults.baseURL).toBe("/api");
  });
});

// Failed requests are logged once, after any token refresh: warn for 4xx, error for 5xx or no response.
describe("failed request logging", () => {
  const failWith = (status?: number, detail?: unknown) => async (config: InternalAxiosRequestConfig) => {
    const response = status === undefined ? undefined
      : ({ status, statusText: "", headers: {}, config, data: { detail } } as AxiosResponse);
    throw new AxiosError("Request failed", status === undefined ? "ERR_NETWORK" : "ERR_BAD_RESPONSE", config, null, response);
  };
  let warn: ReturnType<typeof vi.spyOn>;
  let error: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    error = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(getAccessToken).mockReturnValue("t");
  });
  afterEach(() => vi.restoreAllMocks());

  it("warns on a client error with method, url, status and reason, without the query string", async () => {
    await expect(dtApiAxios.post("/datasets/uploads?x=1", {}, { adapter: failWith(400, "Upload incomplete") })).rejects.toThrow();
    expect(warn).toHaveBeenCalledWith("[HTTP] POST /api/datasets/uploads -> 400: Upload incomplete");
    expect(error).not.toHaveBeenCalled();
  });

  it("errors on a server error", async () => {
    await expect(axios.get("/tools/plugin/p1/cwl", { adapter: failWith(502, "SEEK is down") })).rejects.toThrow();
    expect(error).toHaveBeenCalledWith("[HTTP] GET /api/builder/tools/plugin/p1/cwl -> 502: SEEK is down");
  });

  it("errors on a request with no response", async () => {
    await expect(axios.get("/tools/", { adapter: failWith() })).rejects.toThrow();
    expect(error).toHaveBeenCalledWith("[HTTP] GET /api/builder/tools/ -> network error: Request failed");
  });

  it("logs a structured reason as JSON", async () => {
    await expect(dtApiAxios.get("/models", { adapter: failWith(422, [{ msg: "field required" }]) })).rejects.toThrow();
    expect(warn).toHaveBeenCalledWith('[HTTP] GET /api/models -> 422: [{"msg":"field required"}]');
  });

  it("does not log a cancelled request", async () => {
    const cancelled = async () => { throw new CanceledError(); };
    await expect(axios.get("/tools/", { adapter: cancelled })).rejects.toThrow();
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it("does not log a 401 that succeeds after the token refresh", async () => {
    vi.mocked(getKeycloak).mockReturnValue({ updateToken: vi.fn(async () => true), token: "fresh" } as any);
    let calls = 0;
    const adapter = async (config: InternalAxiosRequestConfig) => {
      if (calls++ === 0) return failWith(401, "expired")(config);
      return { status: 200, statusText: "", headers: {}, config, data: {} } as AxiosResponse;
    };
    await expect(axios.get("/tools/", { adapter })).resolves.toBeTruthy();
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it("logs a retried request that fails again only once", async () => {
    vi.mocked(getKeycloak).mockReturnValue({ updateToken: vi.fn(async () => true), token: "fresh" } as any);
    let calls = 0;
    const adapter = async (config: InternalAxiosRequestConfig) =>
      calls++ === 0 ? failWith(401, "expired")(config) : failWith(500, "boom")(config);
    await expect(axios.get("/tools/", { adapter })).rejects.toThrow();
    expect(error).toHaveBeenCalledTimes(1);
    expect(error).toHaveBeenCalledWith("[HTTP] GET /api/builder/tools/ -> 500: boom");
  });
});
