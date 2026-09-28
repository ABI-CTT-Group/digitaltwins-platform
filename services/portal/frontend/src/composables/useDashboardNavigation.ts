import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { BREADCRUMB_ORDER } from "@/composables/useDashboardData";

/**
 * URL-driven drill-down navigation. The entire drill state is encoded in the
 * route query as `trail` — a comma-separated list of seekIds from the root
 * down to the current level. This is the single source of truth: refreshing,
 * deep-linking, and browser back/forward all "just work", and returning from
 * the assay report never loses progress.
 *
 *   /study-dashboard                         → Programmes
 *   /study-dashboard?trail=prog1             → Projects of prog1
 *   /study-dashboard?trail=prog1,proj2       → Investigations of proj2
 */
export function useDashboardNavigation() {
  const route = useRoute();
  const router = useRouter();

  /** Current trail of seekIds parsed from the URL. */
  const trail = computed<string[]>(() => {
    const raw = route.query.trail;
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (!value) return [];
    return String(value)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  });

  /** Category of the level currently shown. */
  const currentCategory = computed(
    () => BREADCRUMB_ORDER[trail.value.length] ?? "Assays",
  );

  /** Whether the current level can drill any deeper. */
  const canDrill = computed(() => currentCategory.value !== "Assays");

  const pushTrail = (next: string[]) => {
    const query = { ...route.query };
    if (next.length) query.trail = next.join(",");
    else delete query.trail;
    router.push({ query });
  };

  /** Drill into a child node (append its seekId to the trail). */
  const drill = (seekId: string) => {
    if (!canDrill.value) return;
    pushTrail([...trail.value, seekId]);
  };

  /** Jump to the root (Programmes). */
  const goToRoot = () => pushTrail([]);

  /**
   * Jump to a breadcrumb. `depth` is the number of trail entries to keep, i.e.
   * crumb index + 1 (crumb 0 = first trail entry → keep 1).
   */
  const goToDepth = (depth: number) => pushTrail(trail.value.slice(0, depth));

  return { trail, currentCategory, canDrill, drill, goToRoot, goToDepth };
}
