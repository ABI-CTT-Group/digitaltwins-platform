import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";
import StudyDashboardPage from "@/views/study-dashboard/StudyDashboardPage.vue";

describe("study dashboard routes", () => {
  it("serves the study dashboard at /study-dashboard, to admins, researchers and clinicians", () => {
    const route = router.resolve({ name: "StudyDashboardPrototype" });
    expect(route.path).toBe("/study-dashboard");
    expect(route.matched.at(-1)?.components?.default).toBe(StudyDashboardPage);
    expect(route.meta).toMatchObject({ requiresAuth: true, requiresRoles: ["admin", "researcher", "clinician"] });
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
