// Which view of the study dashboard (prototype) to show. A clinician gets the studies to review,
// a researcher the programmes down to studies; admin, or anyone with both roles, picks with "View as".
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth_store";

export type DashboardView = "clinician" | "researcher";

const STORAGE_KEY = "study-dashboard-view";

/** The views a user may see, clinician first (the order of the switch). */
export function viewsFor(roles: { admin: boolean; researcher: boolean; clinician: boolean }): DashboardView[] {
  return [
    ...(roles.admin || roles.clinician ? ["clinician" as const] : []),
    ...(roles.admin || roles.researcher ? ["researcher" as const] : []),
  ];
}

/** The URL's ?view, then a drill-down trail (researcher), then the last choice, then researcher. */
export function chooseView(
  views: DashboardView[],
  { asked, hasTrail, stored }: { asked: string | null; hasTrail: boolean; stored: string | null },
): DashboardView {
  const allowed = (v: string | null): v is DashboardView => views.includes(v as DashboardView);
  if (allowed(asked)) return asked;
  if (hasTrail && allowed("researcher")) return "researcher";
  if (allowed(stored)) return stored;
  return allowed("researcher") ? "researcher" : "clinician";
}

const readStored = () => { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } };
const writeStored = (v: DashboardView) => { try { localStorage.setItem(STORAGE_KEY, v); } catch { /* private window */ } };

export function useStudyDashboardView() {
  const auth = useAuthStore();
  const route = useRoute();
  const router = useRouter();
  const stored = ref(readStored());

  const views = computed(() => viewsFor({
    admin: auth.hasAdminRole, researcher: auth.hasResearcherRole, clinician: auth.hasClinicianRole,
  }));
  const view = computed(() => chooseView(views.value, {
    asked: typeof route.query.view === "string" ? route.query.view : null,
    hasTrail: Boolean(route.query.trail),
    stored: stored.value,
  }));

  /** Opens the top level of a view, and remembers it for the next visit. */
  function choose(v: DashboardView) {
    stored.value = v;
    writeStored(v);
    router.push({ name: "StudyDashboardPrototype", query: { view: v } });
  }

  return { views, view, choose };
}
