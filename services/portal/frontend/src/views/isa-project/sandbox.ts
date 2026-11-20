// The "Te Whatu Ora Radiology Reporting" programme of the Study dashboard (prototype). It turns the ISA projects in the
// browser's store into dashboard items, so the dashboard's drill-down parts can show them without the
// API. Sandbox ids are "te-whatu-ora-radiology-reporting[:project[:investigation[:study[:assay]]]]".
import type { DashboardCategory } from "@/models/types";
import { BREADCRUMB_ORDER, type ResolvedLevel } from "@/composables/useDashboardData";
import type { Catalogue, IsaProject } from "./model/types";

export const SANDBOX_ID = "te-whatu-ora-radiology-reporting";

export interface IsaProjectEntry {
  project: IsaProject;
  source: "example" | "upload";
  /** The fixture an example came from, so it can be reset. */
  exampleId?: string;
  /** Datasets, workflows and tools that came with the project in a bundle (not on the platform). */
  bundled?: Catalogue;
  /** A simulated approval of an upload: it creates the SEEK project and registers the bundled items. */
  approval?: { state: "approving"; stage: string } | { state: "approved" };
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const isSandboxId = (id: string) => id === SANDBOX_ID || id.startsWith(`${SANDBOX_ID}:`);

export function sandboxProgramme(entries: IsaProjectEntry[]): DashboardCategory {
  return {
    seekId: SANDBOX_ID,
    name: "Te Whatu Ora Radiology Reporting",
    category: "Programmes",
    description: plural(entries.length, "project"),
  };
}

export function parseSandboxId(id: string): { projectId?: string; investigationId?: string; studyId?: string } | null {
  if (!isSandboxId(id)) return null;
  const [, projectId, investigationId, studyId] = id.split(":");
  return Object.fromEntries(
    Object.entries({ projectId, investigationId, studyId }).filter(([, v]) => v !== undefined),
  );
}

/** Children of a sandbox node, in the shape the dashboard's data layer returns. */
export function sandboxChildren(parentId: string, parentCategory: string, entries: IsaProjectEntry[]): DashboardCategory[] {
  const ids = parseSandboxId(parentId);
  if (!ids) return [];
  if (parentCategory === "Programmes") {
    return entries.map(({ project }) => ({
      seekId: `${SANDBOX_ID}:${project.project.id}`,
      name: project.project.title,
      category: "Projects",
      description: plural(project.investigations.length, "investigation"),
    }));
  }
  const project = entries.find(e => e.project.project.id === ids.projectId)?.project;
  if (!project) return [];
  if (parentCategory === "Projects") {
    return project.investigations.map(i => ({
      seekId: `${parentId}:${i.id}`, name: i.title, category: "Investigations",
      description: plural(i.studies.length, "study", "studies"),
    }));
  }
  const inv = project.investigations.find(i => i.id === ids.investigationId);
  if (parentCategory === "Investigations") {
    return (inv?.studies ?? []).map(s => ({
      seekId: `${parentId}:${s.id}`, name: s.title, category: "Studies", description: plural(s.assays.length, "assay"),
    }));
  }
  const study = inv?.studies.find(s => s.id === ids.studyId);
  if (parentCategory === "Studies") {
    return (study?.assays ?? []).map(a => ({
      seekId: `${parentId}:${a.id}`, name: a.title, category: "Assays", tag: a.type,
    }));
  }
  return [];
}

/** The level at the end of a trail of sandbox ids. Stops at an id it can't find, like the real dashboard. */
export function resolveSandboxTrail(trail: string[], entries: IsaProjectEntry[]): ResolvedLevel {
  let items = [sandboxProgramme(entries)];
  const breadcrumbs: ResolvedLevel["breadcrumbs"] = [];
  for (const [depth, seekId] of trail.entries()) {
    const node = items.find(item => item.seekId === seekId);
    if (!node) break;
    breadcrumbs.push({ seekId: node.seekId, name: node.name, category: node.category });
    items = sandboxChildren(node.seekId, BREADCRUMB_ORDER[depth], entries);
  }
  return { items, breadcrumbs, currentCategory: BREADCRUMB_ORDER[breadcrumbs.length] ?? "Assays" };
}
