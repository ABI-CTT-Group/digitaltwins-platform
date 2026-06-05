import { ref } from "vue";
import {
  useDashboardProgrammes,
  useDashboardCategoryChildren,
} from "@/bootstrap/dashboard_api";
import { DashboardCategory } from "@/models/types";

/**
 * The SEEK hierarchy, top to bottom. The category at depth `d` is the kind of
 * item shown when the drill-down trail has `d` entries:
 *   trail = []                → Programmes
 *   trail = [progId]          → Projects
 *   trail = [progId, projId]  → Investigations  … and so on.
 */
export const BREADCRUMB_ORDER = [
  "Programmes",
  "Projects",
  "Investigations",
  "Studies",
  "Assays",
] as const;

export type DashboardLevelCategory = (typeof BREADCRUMB_ORDER)[number];

/** One-line description of a level, shown in the dashboard header. */
export function describeCategory(category: string): string {
  switch (category) {
    case "Programmes":
      return "A Programme is an umbrella to group one or more Projects.";
    case "Projects":
      return "A Project represents research activities conducted by a group of one or more people.";
    case "Investigations":
      return "Investigation is a high level description of the research carried out within a particular project.";
    case "Studies":
      return "A Study is a particular hypothesis, which you are planning to test, using various techniques. A Study must belong to one Investigation and it can contain one or more Assays.";
    case "Assays":
      return "An Assay is a single workflow execution against a study cohort.";
    default:
      return "";
  }
}

// Children-list cache, shared across every `useDashboardData()` call and — being
// module-scoped — surviving DashboardView unmount/remount. This is what makes a
// round-trip to the assay report (a separate route) return to the dashboard
// WITHOUT re-hitting the backend for the whole trail. Keyed by
// `parentSeekId::category`; the root programmes list uses ROOT_KEY.
//
// Trade-off: cached for the app session, so items added externally (e.g. via
// SEEK) won't appear until a full page reload. Call `clearDashboardCache()` if a
// deliberate refresh is ever needed.
const ROOT_KEY = "__root__";
const childrenCache = new Map<string, DashboardCategory[]>();

const cacheKey = (parentSeekId: string, parentCategory: string) =>
  `${parentSeekId}::${parentCategory}`;

/** Drop all cached lists so the next load re-fetches from the backend. */
export function clearDashboardCache() {
  childrenCache.clear();
}

/**
 * A resolved drill-down level: the items to render at the current depth plus the
 * breadcrumb trail (with display names) needed to render the header.
 */
export interface ResolvedLevel {
  /** Items shown in the grid at the current depth. */
  items: DashboardCategory[];
  /** One crumb per trail entry, in order, with the resolved display name. */
  breadcrumbs: Array<{ seekId: string; name: string; category: string }>;
  /** Category of the items currently shown (= BREADCRUMB_ORDER[trail.length]). */
  currentCategory: DashboardLevelCategory;
}

/**
 * Data layer for the dashboard. Owns network access + an in-memory cache keyed
 * by `parentSeekId::category`, and resolves a full level from a trail of
 * seekIds. The drill-down trail itself lives in the URL, never here.
 */
export function useDashboardData() {
  const loading = ref(false);
  const error = ref<string | null>(null);

  /** Top-level programmes, cached. */
  async function getProgrammes(): Promise<DashboardCategory[]> {
    const cached = childrenCache.get(ROOT_KEY);
    if (cached) return cached;
    const programmes = (await useDashboardProgrammes()) ?? [];
    childrenCache.set(ROOT_KEY, programmes);
    return programmes;
  }

  /**
   * Children of a node. `parentCategory` is the category of the parent node
   * being expanded (e.g. expanding a Programme passes "Programmes").
   */
  async function getChildren(
    parentSeekId: string,
    parentCategory: string,
  ): Promise<DashboardCategory[]> {
    const key = cacheKey(parentSeekId, parentCategory);
    const cached = childrenCache.get(key);
    if (cached) return cached;
    const children = (await useDashboardCategoryChildren(parentSeekId, parentCategory)) ?? [];
    childrenCache.set(key, children);
    return children;
  }

  /**
   * Walk a trail of seekIds from the root, returning the items to show at the
   * end of the trail plus named breadcrumbs. `typeFilter` is applied only to
   * the root programmes list (study vs clinician split).
   *
   * Tolerant of stale/invalid trails: if a seekId can't be found at its level,
   * the trail is truncated there and the caller can re-sync the URL.
   */
  async function loadTrail(
    trail: string[],
    typeFilter: (item: DashboardCategory) => boolean,
  ): Promise<ResolvedLevel> {
    loading.value = true;
    error.value = null;
    try {
      // Level 0 is the (filtered) programmes list.
      let currentList = (await getProgrammes())
        .filter(typeFilter)
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name));

      const breadcrumbs: ResolvedLevel["breadcrumbs"] = [];

      for (let depth = 0; depth < trail.length; depth++) {
        const seekId = trail[depth];
        const node = currentList.find((item) => item.seekId === seekId);
        if (!node) break; // stale trail — stop here, degrade gracefully

        breadcrumbs.push({ seekId: node.seekId, name: node.name, category: node.category });
        currentList = await getChildren(node.seekId, BREADCRUMB_ORDER[depth]);
      }

      const currentCategory = BREADCRUMB_ORDER[breadcrumbs.length] ?? "Assays";
      return { items: currentList, breadcrumbs, currentCategory };
    } catch (e: any) {
      error.value = e?.message ?? "Failed to load dashboard data.";
      return { items: [], breadcrumbs: [], currentCategory: "Programmes" };
    } finally {
      loading.value = false;
    }
  }

  return { loading, error, getProgrammes, getChildren, loadTrail };
}
