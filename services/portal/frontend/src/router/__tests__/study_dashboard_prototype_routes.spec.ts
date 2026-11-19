import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";

describe("study dashboard routes", () => {
  it("serves the ISA projects' study dashboard at /study-dashboard, for admins only", () => {
    const route = router.resolve({ name: "StudyDashboardPrototype" });
    expect(route.path).toBe("/study-dashboard");
    expect(route.meta).toMatchObject({ requiresAuth: true, requiresRoles: ["admin"] });
  });

  it("moves the platform's study dashboard to an unlisted URL", () => {
    const route = router.resolve({ name: "StudyDashboard" });
    expect(route.path).toBe("/study-dashboard-platform");
    expect(route.meta).toMatchObject({ requiresAuth: true, requiresRoles: ["admin", "researcher"] });
  });

  it("keeps the old prototype URL working", () => {
    const record = router.getRoutes().find((r) => r.path === "/study-dashboard-prototype");
    expect(record?.redirect).toEqual({ name: "StudyDashboardPrototype" });
  });
});
