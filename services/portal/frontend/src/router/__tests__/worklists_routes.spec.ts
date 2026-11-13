import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";

describe("clinician dashboard routes", () => {
  it("serves the worklist page as the clinician dashboard, to admins, researchers and clinicians", () => {
    const r = router.resolve({ name: "ClinicianDashboard" });
    expect(r.path).toBe("/clinician-dashboard");
    expect(r.meta.requiresRoles).toEqual(["admin", "researcher", "clinician"]);
  });

  it("sends /worklists links to the clinician dashboard", () => {
    const old = router.getRoutes().find(r => r.path === "/worklists");
    expect(old?.redirect).toEqual({ name: "ClinicianDashboard" });
  });
});
