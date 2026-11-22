import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";
import WorklistsView from "@/views/worklists/WorklistsView.vue";

const CLINICIAN_VIEW = { name: "StudyDashboardPrototype", query: { view: "clinician" } };
const route = (path: string) => router.getRoutes().find(r => r.path === path);

describe("worklist routes", () => {
  it("opens a study's worklist under the study dashboard, for admins and clinicians", () => {
    const r = router.resolve({ name: "ClinicianStudyWorklist", params: { studyId: "breast-mri-reading" } });
    expect(r.path).toBe("/study-dashboard/reviews/breast-mri-reading");
    expect(r.matched.at(-1)?.components?.default).toBe(WorklistsView);
    expect(r.matched.at(-1)?.props.default).toBe(true);
    expect(r.meta.requiresRoles).toEqual(["admin", "clinician"]);
  });

  it("sends the old clinician dashboard links to the clinician view", () => {
    expect(route("/clinician-dashboard")?.redirect).toEqual(CLINICIAN_VIEW);
    expect(route("/worklists")?.redirect).toEqual(CLINICIAN_VIEW);
  });

  it("sends an old worklist link to the study's worklist", () => {
    const old = route("/clinician-dashboard/studies/:studyId");
    const target = typeof old?.redirect === "function"
      ? old.redirect(router.resolve("/clinician-dashboard/studies/breast-mri-reading"), router.currentRoute.value)
      : old?.redirect;
    expect(router.resolve(target as never).path).toBe("/study-dashboard/reviews/breast-mri-reading");
  });
});
