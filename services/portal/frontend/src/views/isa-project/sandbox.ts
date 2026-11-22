// The programmes of the Study dashboard (prototype): the built-in "Te Whatu Ora Radiology Reporting",
// plus each programme an upload was filed in. It turns the ISA projects in the browser's store into
// dashboard items, so the dashboard's drill-down parts can show them without the API. Sandbox ids are
// "<programme>[:project[:investigation[:study[:assay]]]]"; a named programme's id is "isa-<slug>".
import type { DashboardCategory } from "@/models/types";
import { BREADCRUMB_ORDER, type ResolvedLevel } from "@/composables/useDashboardData";
import type { Catalogue, IsaProject } from "./model/types";

export const SANDBOX_ID = "te-whatu-ora-radiology-reporting";
const NAMED_PREFIX = "isa-";

export interface Programme { id: string; name: string }
/** Where every example, and every project stored before programmes could be chosen, is filed. */
export const BUILT_IN_PROGRAMME: Programme = { id: SANDBOX_ID, name: "Te Whatu Ora Radiology Reporting" };

export interface IsaProjectEntry {
  project: IsaProject;
  source: "example" | "upload";
  /** The fixture an example came from, so it can be reset. */
  exampleId?: string;
  /** Which release of that fixture this browser stored (EXAMPLE_RELEASE when it was added). */
  exampleRelease?: number;
  /** Datasets, workflows and tools that came with the project in a bundle (not on the platform). */
  bundled?: Catalogue;
  /** A simulated approval of an upload: it creates the SEEK project and registers the bundled items. */
  approval?: { state: "approving"; stage: string } | { state: "approved" };
  /** The programme the upload was filed in; none means the built-in one. */
  programme?: Programme;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const programmeOf = (e: IsaProjectEntry): Programme => e.programme ?? BUILT_IN_PROGRAMME;

/** The built-in programme, then each programme a project is filed in, in the order first used. */
export function knownProgrammes(entries: IsaProjectEntry[]): Programme[] {
  const all = [BUILT_IN_PROGRAMME, ...entries.map(programmeOf)];
  return all.filter((p, n) => all.findIndex(q => q.id === p.id) === n);
}

/** "Ōtautahi imaging" → "otautahi-imaging": accents dropped, anything else not a–z or 0–9 a hyphen. */
const slug = (name: string) => name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** The programme a typed name means: a known one with the same name (ignoring case and spacing), or a new one. */
export function programmeNamed(name: string, entries: IsaProjectEntry[]): Programme {
  const clean = name.trim().replace(/\s+/g, " ");
  const known = knownProgrammes(entries).find(p => slug(p.name) === slug(clean));
  return known ?? { id: `${NAMED_PREFIX}${slug(clean) || "programme"}`, name: clean };
}

export const isSandboxId = (id: string) => {
  const programmeId = id.split(":")[0];
  return programmeId === SANDBOX_ID || programmeId.startsWith(NAMED_PREFIX);
};

export function sandboxProgrammes(entries: IsaProjectEntry[]): DashboardCategory[] {
  return knownProgrammes(entries).map(p => ({
    seekId: p.id,
    name: p.name,
    category: "Programmes",
    description: plural(entries.filter(e => programmeOf(e).id === p.id).length, "project"),
  }));
}

export function parseSandboxId(id: string):
  { programmeId: string; projectId?: string; investigationId?: string; studyId?: string } | null {
  if (!isSandboxId(id)) return null;
  const [programmeId, projectId, investigationId, studyId] = id.split(":");
  return {
    programmeId,
    ...Object.fromEntries(Object.entries({ projectId, investigationId, studyId }).filter(([, v]) => v !== undefined)),
  };
}

/** Children of a sandbox node, in the shape the dashboard's data layer returns. */
export function sandboxChildren(parentId: string, parentCategory: string, entries: IsaProjectEntry[]): DashboardCategory[] {
  const ids = parseSandboxId(parentId);
  if (!ids) return [];
  if (parentCategory === "Programmes") {
    return entries.filter(e => programmeOf(e).id === ids.programmeId).map(({ project }) => ({
      seekId: `${parentId}:${project.project.id}`,
      name: project.project.title,
      category: "Projects",
      description: plural(project.investigations.length, "investigation"),
    }));
  }
  const project = entries.find(e => e.project.project.id === ids.projectId && programmeOf(e).id === ids.programmeId)?.project;
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
  let items = sandboxProgrammes(entries);
  const breadcrumbs: ResolvedLevel["breadcrumbs"] = [];
  for (const [depth, seekId] of trail.entries()) {
    const node = items.find(item => item.seekId === seekId);
    if (!node) break;
    breadcrumbs.push({ seekId: node.seekId, name: node.name, category: node.category });
    items = sandboxChildren(node.seekId, BREADCRUMB_ORDER[depth], entries);
  }
  return { items, breadcrumbs, currentCategory: BREADCRUMB_ORDER[breadcrumbs.length] ?? "Assays" };
}
