// An ISA project bundle (prototype): one folder or .zip with the ISA project JSON at its root and,
// under datasets/<id>/, each dataset, workflow or tool the design uses that isn't on the platform
// yet. Nothing is uploaded: only file counts, sizes and the workflow CWL are read and kept.
import type { LocalSource } from "@/bootstrap/upload_source";
import { findRootPrefix, formatBytes } from "@/composables/useFolderScan";
import { SDS_MARKER, sdsToolCwls, sdsWorkflowCwls } from "@/views/upload-dataset/components/utils";
import { parseCwlText } from "@/views/upload-dataset/components/workflow_cwls";
import { validateIsaProject } from "../model/isaProject";
import type {
  AssayType,
  Catalogue,
  CatalogueTool,
  CatalogueWorkflow,
  Category,
  IsaProject,
  Port,
  BundledFiles,
  WorkflowStep,
} from "../model/types";

export interface BundleFile { path: string; size: number; text: () => Promise<string> }

/** Every file in a picked folder or .zip, with its path inside it. */
export async function bundleFiles(source: LocalSource): Promise<BundleFile[]> {
  if (source.kind === "folder") {
    return source.files.map(f => ({ path: f.webkitRelativePath || f.name, size: f.size, text: () => f.text() }));
  }
  const JSZip = (await import("jszip")).default;
  const zip = await JSZip.loadAsync(source.blob);
  return Object.values(zip.files).filter(e => !e.dir).map(e => ({
    path: e.name,
    // JSZip keeps the unpacked size only on its internal record.
    size: (e as unknown as { _data?: { uncompressedSize?: number } })._data?.uncompressedSize ?? 0,
    text: () => e.async("string"),
  }));
}

export interface BundleRead {
  /** Null while there are errors. */
  project: IsaProject | null;
  /** The bundle's items the design uses, ready to add to the catalogue. */
  bundled: Catalogue;
  errors: string[];
  warnings: string[];
}

type FolderKind = "dataset" | "workflow" | "tool";

const CATEGORIES: Category[] = ["measurements", "models", "tools", "workflows"];
const ASSAY_TYPES: AssayType[] = ["script", "notebook", "gui"];

// The JSON isn't validated yet when the folders are read, so walk it defensively.
type Loose = Record<string, unknown>;
const list = (v: unknown): Loose[] => (Array.isArray(v) ? v.filter(x => typeof x === "object" && x !== null) : []);
const assaysIn = (json: unknown) =>
  list((json as Loose)?.investigations).flatMap(i => list(i.studies)).flatMap(s => list(s.assays));
const inputsOf = (a: Loose) => list(a.inputs).map(i => ({ port: i.port, source: (i.source ?? null) as Loose | null }));

/** CWL ports and steps come as a map (`{id: …}`) or a list (`[{id, …}]`). */
const cwlEntries = (section: unknown): [string, Loose][] => {
  if (Array.isArray(section)) return section.map(s => [String(s?.id).replace(/^#/, ""), s]);
  return typeof section === "object" && section !== null ? Object.entries(section as Record<string, Loose>) : [];
};
/** A port's category is its CWL `doc`, as in the platform's SDS workflow packages. */
const ports = (section: unknown): Port[] => cwlEntries(section).map(([name, def]) => ({
  name,
  category: CATEGORIES.includes(def?.doc as Category) ? (def.doc as Category) : "measurements",
}));

const stats = (files: BundleFile[]): BundledFiles =>
  ({ fileCount: files.length, bytes: files.reduce((n, f) => n + f.size, 0) });

/** File names directly in a folder's primary/. */
const primaryNames = (id: string, files: BundleFile[]) => files
  .map(f => f.path.slice(`datasets/${id}/`.length).split("/"))
  .filter(p => p.length === 2 && p[0] === "primary")
  .map(p => p[1]);

/** Read a bundle: find the JSON, turn each folder the design uses into a catalogue item, then
 *  check the design against the platform catalogue plus those items. */
export async function readBundle(all: BundleFile[], catalogue: Catalogue): Promise<BundleRead> {
  const bundled: Catalogue = { datasets: [], workflows: [], tools: [] };
  const fail = (errors: string[]): BundleRead => ({ project: null, bundled, errors, warnings: [] });

  const prefix = findRootPrefix(all.map(f => ({ path: f.path, isDir: false })));
  const files = all.filter(f => f.path.startsWith(prefix)).map(f => ({ ...f, path: f.path.slice(prefix.length) }));

  const roots = files.filter(f => !f.path.includes("/") && f.path.toLowerCase().endsWith(".json"))
    .sort((a, b) => a.path.localeCompare(b.path));
  if (roots.length !== 1) {
    const found = roots.length ? `${roots.length}: ${roots.map(f => f.path).join(", ")}` : "none";
    return fail([`The bundle needs one .json file at its root, the ISA project; it has ${found}.`]);
  }
  let json: unknown;
  try {
    json = JSON.parse(await roots[0].text());
  } catch {
    return fail([`${roots[0].path} is not valid JSON.`]);
  }

  const folders = new Map<string, BundleFile[]>();
  for (const f of files) {
    const m = /^datasets\/([^/]+)\/./.exec(f.path);
    if (!m) continue;
    if (!folders.has(m[1])) folders.set(m[1], []);
    folders.get(m[1])!.push(f);
  }
  const kinds = new Map<string, FolderKind>();
  for (const [id, fs] of folders) {
    const names = primaryNames(id, fs);
    kinds.set(id, sdsWorkflowCwls(names).length ? "workflow" : sdsToolCwls(names).length ? "tool" : "dataset");
  }

  const assays = assaysIn(json);
  const onPlatform = new Set([...catalogue.datasets, ...catalogue.workflows, ...catalogue.tools].map(x => x.id));
  const wantedWorkflows = new Set(assays.map(a => a.workflowId).filter((id): id is string => typeof id === "string"));
  const wantedDatasets = new Set(assays.flatMap(a => inputsOf(a))
    .flatMap(i => (i.source?.kind === "existing" && typeof i.source.datasetId === "string" ? [i.source.datasetId] : [])));
  const errors: string[] = [];
  const used = new Set<string>();

  // Tool packages, by the tool name a workflow step's CWL file gives.
  const toolPackages = new Map<string, string>();
  for (const [id, fs] of folders) {
    if (kinds.get(id) !== "tool") continue;
    for (const file of sdsToolCwls(primaryNames(id, fs))) toolPackages.set(file.replace(/\.cwl$/, ""), id);
  }
  const report = (e: string) => { if (!errors.includes(e)) errors.push(e); };
  // Every folder the design uses is an SDS package, as the platform registers it.
  const isSds = (id: string) => folders.get(id)!.some(f => f.path === `datasets/${id}/${SDS_MARKER}`);
  const notSds = (id: string) => `datasets/${id}/ isn't an SDS package: it needs ${SDS_MARKER} at its root.`;

  const addTool = (tool: CatalogueTool) => {
    if (!bundled.tools.some(t => t.id === tool.id)) bundled.tools.push(tool);
  };

  for (const [id, fs] of folders) {
    if (kinds.get(id) !== "workflow" || !wantedWorkflows.has(id) || onPlatform.has(id)) continue;
    used.add(id);
    if (!isSds(id)) { report(notSds(id)); continue; }
    const names = primaryNames(id, fs);
    const cwls = sdsWorkflowCwls(names);
    if (cwls.length !== 1) {
      errors.push(`datasets/${id}/: a workflow package needs exactly one primary/workflow_*.cwl; it has ${cwls.length}.`);
      continue;
    }
    const path = `datasets/${id}/primary/${cwls[0]}`;
    let cwl: Loose;
    try {
      cwl = (parseCwlText(await fs.find(f => f.path === path)!.text()) ?? {}) as Loose;
    } catch (e) {
      errors.push(`${path} can't be read: ${e instanceof Error ? e.message.split("\n")[0] : String(e)}`);
      continue;
    }
    const usedAs = assays.find(a => a.workflowId === id)?.type as AssayType;
    const type = ASSAY_TYPES.includes(usedAs) ? usedAs : "script";
    const steps: WorkflowStep[] = [];
    for (const [stepId, def] of cwlEntries(cwl.steps)) {
      const file = String(def?.run).split("/").pop()!;
      const name = file.replace(/\.cwl$/, "");
      const platformTool = catalogue.tools.find(t => t.name === name);
      const toolPackage = toolPackages.get(name);
      if (platformTool) {
        steps.push({ id: stepId, toolId: platformTool.id });
      } else if (names.includes(file)) {
        addTool({ id: name, name, type, bundled: stats(fs.filter(f => f.path === `datasets/${id}/primary/${file}`)) });
        steps.push({ id: stepId, toolId: name });
      } else if (toolPackage) {
        used.add(toolPackage);
        if (!isSds(toolPackage)) { report(notSds(toolPackage)); continue; }
        addTool({ id: toolPackage, name, type, bundled: stats(folders.get(toolPackage)!) });
        steps.push({ id: stepId, toolId: toolPackage });
      } else {
        errors.push(`datasets/${id}/: step ${stepId} runs ${file}, which is neither in primary/, ` +
          "in a tool package in the bundle, nor on the platform.");
      }
    }
    const workflow: CatalogueWorkflow = {
      id, name: cwls[0].replace(/\.cwl$/, ""), type,
      inputs: ports(cwl.inputs), outputs: ports(cwl.outputs), steps, cwl, bundled: stats(fs),
    };
    bundled.workflows.push(workflow);
  }

  const workflows = [...catalogue.workflows, ...bundled.workflows];
  for (const [id, fs] of folders) {
    if (kinds.get(id) !== "dataset" || !wantedDatasets.has(id) || onPlatform.has(id)) continue;
    used.add(id);
    if (!isSds(id)) { report(notSds(id)); continue; }
    if (!fs.some(f => f.path.startsWith(`datasets/${id}/primary/`))) {
      report(`datasets/${id}/ has no files under primary/.`);
      continue;
    }
    // The dataset takes the category of the workflow inputs that read it, which must agree.
    const readers = assays.flatMap(a => inputsOf(a)
      .filter(i => i.source?.kind === "existing" && i.source.datasetId === id)
      .map(i => ({
        at: `assay ${a.id} input ${i.port}`,
        category: workflows.find(w => w.id === a.workflowId)?.inputs.find(p => p.name === i.port)?.category ?? "measurements",
      })));
    const first = readers[0];
    const other = readers.find(r => r.category !== first.category);
    if (other) {
      report(`datasets/${id}/ is read as ${first.category} by ${first.at} and as ${other.category} by ${other.at}; ` +
        "a dataset has one category.");
      continue;
    }
    bundled.datasets.push({ id, name: id, category: first.category, bundled: stats(fs) });
  }

  const warnings: string[] = [];
  for (const id of folders.keys()) {
    if (used.has(id) || (!onPlatform.has(id) && (wantedDatasets.has(id) || wantedWorkflows.has(id)))) continue;
    warnings.push(onPlatform.has(id)
      ? `datasets/${id}/ is already on the platform; the design uses the platform's copy, so this folder is left out.`
      : `datasets/${id}/ isn't used by the design, so it is left out.`);
  }

  // Say which folder an unknown id needs. A workflow folder that failed already has its own error.
  const withHint = (e: string): string | null => {
    const m = /: unknown (dataset|workflow) (\S+)$/.exec(e);
    if (!m) return e;
    const [, what, id] = m;
    const kind = kinds.get(id);
    if (!kind) return `${e} (no datasets/${id}/ folder in the bundle)`;
    if (kind === what) return null;
    return what === "workflow"
      ? `${e} (datasets/${id}/ has no primary/workflow_*.cwl)`
      : `${e} (datasets/${id}/ is a ${kind} package, not a dataset)`;
  };
  const result = validateIsaProject(json, withBundled(catalogue, bundled));
  if (!result.ok) errors.push(...result.errors.map(withHint).filter((e): e is string => e !== null));

  return { project: errors.length || !result.ok ? null : result.project, bundled, errors, warnings };
}

/** The platform catalogue plus a bundle's items. */
export function withBundled(catalogue: Catalogue, bundled: Catalogue | undefined): Catalogue {
  if (!bundled) return catalogue;
  return {
    datasets: [...catalogue.datasets, ...bundled.datasets],
    workflows: [...catalogue.workflows, ...bundled.workflows],
    tools: [...catalogue.tools, ...bundled.tools],
  };
}

export interface ManifestRow { kind: FolderKind; id: string; name: string; meta: string; usedBy: string[] }

const plural = (n: number, one: string) => `${n} ${n === 1 ? one : `${one}s`}`;
const unique = (xs: string[]) => [...new Set(xs)];

/** What a bundle adds and who uses each item, and how many of the design's items are already on
 *  the platform, for the upload review. */
export function bundleManifest(project: IsaProject, bundled: Catalogue, catalogue: Catalogue) {
  const assays = project.investigations.flatMap(i => i.studies).flatMap(s => s.assays);
  const datasetIds = unique(assays.flatMap(a => a.inputs)
    .flatMap(i => (i.source?.kind === "existing" ? [i.source.datasetId] : [])));
  const readers = (id: string) => unique(assays
    .filter(a => a.inputs.some(i => i.source?.kind === "existing" && i.source.datasetId === id)).map(a => a.title));
  const rows: ManifestRow[] = [
    ...bundled.datasets.map(d => ({
      kind: "dataset" as const, id: d.id, name: d.name, usedBy: readers(d.id),
      meta: `${d.category}, ${plural(d.bundled?.fileCount ?? 0, "file")}, ${formatBytes(d.bundled?.bytes ?? 0)}`,
    })),
    ...bundled.workflows.map(w => ({
      kind: "workflow" as const, id: w.id, name: w.name,
      usedBy: unique(assays.filter(a => a.workflowId === w.id).map(a => a.title)),
      meta: `${w.type}, ${plural(w.steps.length, "step")}, ${plural(w.bundled?.fileCount ?? 0, "file")}`,
    })),
    ...bundled.tools.map(t => ({
      kind: "tool" as const, id: t.id, name: t.name, meta: t.type,
      usedBy: bundled.workflows.filter(w => w.steps.some(s => s.toolId === t.id)).map(w => w.name),
    })),
  ];
  const has = (items: { id: string }[], id: string) => items.some(x => x.id === id);
  return {
    rows,
    onPlatform: {
      datasets: datasetIds.filter(id => has(catalogue.datasets, id)).length,
      workflows: unique(assays.flatMap(a => (a.workflowId ? [a.workflowId] : [])))
        .filter(id => has(catalogue.workflows, id)).length,
      tools: unique(bundled.workflows.flatMap(w => w.steps.map(s => s.toolId)))
        .filter(id => has(catalogue.tools, id)).length,
    },
  };
}
