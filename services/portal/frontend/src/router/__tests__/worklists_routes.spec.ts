import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";

describe("worklists routes", () => {
  it("serves Worklists at /worklists to the clinician dashboard's roles", () => {
    const r = router.resolve({ name: "Worklists" });
    expect(r.path).toBe("/worklists");
    expect(r.meta.requiresRoles).toEqual(["admin", "researcher", "clinician"]);
  });

  it("sends the old clinician dashboard URL to Worklists", () => {
    const old = router.getRoutes().find(r => r.path === "/clinician-dashboard");
    expect(old?.redirect).toEqual({ name: "Worklists" });
  });
});
