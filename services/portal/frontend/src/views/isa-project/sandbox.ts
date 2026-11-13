// The study dashboard's "Study design sandbox" programme (prototype). It turns the ISA projects in
// the browser's store into dashboard items, so the existing drill-down can show them without the
// API. Sandbox ids are "isa-sandbox[:project[:investigation[:study[:assay]]]]".
import type { DashboardCategory } from "@/models/types";
import type { Catalogue, IsaProject } from "./model/types";

export const SANDBOX_ID = "isa-sandbox";

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

export const isSandboxId = (id: string) => id === SANDBOX_ID || id.startsWith(`${SANDBOX_ID}:`);

export function sandboxProgramme(): DashboardCategory {
  return {
    seekId: SANDBOX_ID,
    name: "Study design sandbox",
    category: "Programmes",
    description:
      "Plan every assay of a study before anything runs. Pick inputs that earlier assays will produce, " +
      "and see which tools each workflow uses. Holds example and uploaded ISA projects; nothing here is " +
      "saved to the platform.",
  };
}

export function parseSandboxId(id: string): { projectId?: string; investigationId?: string; studyId?: string } | null {
  if (!isSandboxId(id)) return null;
  const [, projectId, investigationId, studyId] = id.split(":");
  return Object.fromEntries(
    Object.entries({ projectId, investigationId, studyId }).filter(([, v]) => v !== undefined),
  );
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Children of a sandbox node, in the shape the dashboard's data layer returns. */
export function sandboxChildren(parentId: string, parentCategory: string, entries: IsaProjectEntry[]): DashboardCategory[] {
  const ids = parseSandboxId(parentId);
  if (!ids) return [];
  if (parentCategory === "Programmes") {
    return entries.map(({ project, source }) => {
      const studies = project.investigations.flatMap(i => i.studies);
      const assays = studies.flatMap(s => s.assays);
      return {
        seekId: `${SANDBOX_ID}:${project.project.id}`,
        name: project.project.title,
        category: "Projects",
        description: `${source === "example" ? "Example" : "Uploaded"} ISA project: ` +
          `${plural(project.investigations.length, "investigation")}, ${plural(studies.length, "study", "studies")}, ` +
          `${plural(assays.length, "assay")}.`,
      };
    });
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
