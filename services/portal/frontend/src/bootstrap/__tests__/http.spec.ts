import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ getAccessToken: vi.fn(), getKeycloak: vi.fn() }));

import axios from "axios";
import { dtApiAxios } from "@/bootstrap/http";

// The gateway sends /api/portal/ to the builder and the rest of /api/ to the platform API.
describe("http base URLs", () => {
  it("sends the default client to the portal backend", () => {
    expect(axios.defaults.baseURL).toBe("/api/portal");
  });

  it("sends dtApi to the platform API", () => {
    expect(dtApiAxios.defaults.baseURL).toBe("/api");
  });
});
