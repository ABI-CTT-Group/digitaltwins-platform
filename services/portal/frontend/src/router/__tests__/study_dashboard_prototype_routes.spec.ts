import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";

describe("study dashboard (prototype) route", () => {
  it("serves the prototype next to the real study dashboard, for admins only", () => {
    const route = router.resolve({ name: "StudyDashboardPrototype" });
    expect(route.path).toBe("/study-dashboard-prototype");
    expect(route.meta).toMatchObject({ requiresAuth: true, requiresRoles: ["admin"] });
  });
});
