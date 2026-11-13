import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";
import StudyListView from "@/views/worklists/StudyListView.vue";
import WorklistsView from "@/views/worklists/WorklistsView.vue";

describe("clinician dashboard routes", () => {
  it("serves the clinician dashboard to admins, researchers and clinicians", () => {
    const r = router.resolve({ name: "ClinicianDashboard" });
    expect(r.path).toBe("/clinician-dashboard");
    expect(r.meta.requiresRoles).toEqual(["admin", "researcher", "clinician"]);
  });

  it("lists the clinician's studies on the dashboard", () => {
    const r = router.resolve({ name: "ClinicianDashboard" });
    expect(r.matched.at(-1)?.components?.default).toBe(StudyListView);
  });

  it("opens a study's worklist under the dashboard, with the study id as a prop", () => {
    const r = router.resolve({ name: "ClinicianStudyWorklist", params: { studyId: "breast-mri-reading" } });
    expect(r.path).toBe("/clinician-dashboard/studies/breast-mri-reading");
    expect(r.matched.at(-1)?.components?.default).toBe(WorklistsView);
    expect(r.matched.at(-1)?.props.default).toBe(true);
    expect(r.meta.requiresRoles).toEqual(["admin", "researcher", "clinician"]);
  });

  it("sends /worklists links to the clinician dashboard", () => {
    const old = router.getRoutes().find(r => r.path === "/worklists");
    expect(old?.redirect).toEqual({ name: "ClinicianDashboard" });
  });
});
