// Pure logic for the ISA project prototype: validation, planned datasets, run order and the
// study graph. Components only render what these functions return.
import {
  SCHEMA_VERSION,
  type Assay,
  type AssayOutput,
  type Catalogue,
  type CatalogueWorkflow,
  type Category,
  type InputSource,
  type IsaProject,
  type Study,
} from "./types";

const ASSAY_TYPES = ["script", "notebook", "gui"];
const CATEGORIES = ["measurements", "models", "tools", "workflows"];

export type AssayStatus = "unconfigured" | "blocked" | "ready" | "ran" | "submitted";

/** A simulated study run: assays whose run has finished, and those whose outputs are submitted
 *  (only then do their planned datasets exist). */
export interface Sim { ran: string[]; submitted: string[] }
export const emptySim = (): Sim => ({ ran: [], submitted: [] });

export interface InputOption {
  key: string;
  label: string;
  planned: boolean;
  producedBy?: string;
  /** A dataset that came in an ISA project bundle and isn't on the platform yet. */
  bundled?: true;
  source: InputSource;
}

export interface GraphNode {
  id: string;
  /** An assay, or a dataset already on the platform that feeds one. */
  kind: "assay" | "source";
  label: string;
  column: number;
  row: number;
  status?: AssayStatus;
  assayId?: string;
  /** A source dataset that came in an ISA project bundle and isn't on the platform yet. */
  bundled?: true;
}
/** One edge per pair of nodes, labelled with the planned datasets passing along it (or, from a
 *  platform dataset, with how many inputs it feeds). */
export interface GraphEdge { id: string; source: string; target: string; labels: string[]; planned: boolean }

/** Several outputs of one assay can fill the same dataset, each as its own part, so a planned
 *  dataset is named by the dataset and the output port that fills it. */
const plannedLabel = (datasetName: string, port: string) => `${datasetName} / ${port}`;

/** Each assay type's colour, the same as on the real assay cards. */
export const ASSAY_TYPE_ACCENT: Record<string, string> = { gui: "#5fd6e8", notebook: "#ffb74d", script: "#c792ea" };

export const sourceKey = (s: InputSource): string =>
  s.kind === "existing" ? `existing:${s.datasetId}` : `planned:${s.assayId}:${s.port}`;

/** Ids of the assays whose planned datasets this assay consumes. */
const producers = (a: Assay): string[] =>
  a.inputs.flatMap(i => (i.source?.kind === "planned" ? [i.source.assayId] : []));

// ---- Validation ---------------------------------------------------------------------------

type Validation = { ok: true; project: IsaProject } | { ok: false; errors: string[] };

const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string" && v.length > 0;

// Ids end up in dashboard links (`?trail=a,b` with sandbox ids joined by ":"), so keep them plain.
const ID_PATTERN = /^[A-Za-z0-9_.-]+$/;
function checkId(id: string, what: string, errors: string[]) {
  if (!ID_PATTERN.test(id)) errors.push(`${what} id "${id}": use only letters, digits, ".", "_" and "-"`);
}

function checkSource(s: unknown, at: string, errors: string[]) {
  if (s === null) return;
  const ok = isObj(s) && (
    (s.kind === "existing" && isStr(s.datasetId)) ||
    (s.kind === "planned" && isStr(s.assayId) && isStr(s.port)));
  if (!ok) errors.push(`${at}: source must be null, {kind:"existing",datasetId} or {kind:"planned",assayId,port}`);
}

function checkAssay(a: unknown, at: string, errors: string[]) {
  if (!isObj(a) || !isStr(a.id) || !isStr(a.title)) { errors.push(`${at}: needs an id and a title`); return; }
  checkId(a.id, "assay", errors);
  at = `assay ${a.id}`;
  if (!ASSAY_TYPES.includes(a.type as string)) errors.push(`${at}: type must be one of ${ASSAY_TYPES.join(", ")}`);
  if (a.workflowId !== null && !isStr(a.workflowId)) errors.push(`${at}: workflowId must be a string or null`);
  if (!Array.isArray(a.cohort) || !a.cohort.every(n => Number.isInteger(n) && n > 0))
    errors.push(`${at}: cohort must be a list of subject numbers`);
  if (!Array.isArray(a.inputs)) errors.push(`${at}: inputs must be a list`);
  else a.inputs.forEach((i, n) => {
    if (!isObj(i) || !isStr(i.port)) errors.push(`${at}: inputs[${n}] needs a port`);
    else checkSource(i.source, `${at} input ${i.port}`, errors);
  });
  if (!Array.isArray(a.outputs)) errors.push(`${at}: outputs must be a list`);
  else a.outputs.forEach((o, n) => {
    if (!isObj(o) || !isStr(o.port) || !isStr(o.datasetName) || !CATEGORIES.includes(o.category as string))
      errors.push(`${at}: outputs[${n}] needs a port, a datasetName and a category`);
  });
}

function checkShape(json: Record<string, unknown>, errors: string[]) {
  const p = json.project;
  if (!isObj(p) || !isStr(p.id) || !isStr(p.title)) errors.push("project needs an id and a title");
  else checkId(p.id, "project", errors);
  if (!Array.isArray(json.investigations)) { errors.push("investigations must be a list"); return; }
  json.investigations.forEach((inv, i) => {
    if (!isObj(inv) || !isStr(inv.id) || !isStr(inv.title) || !Array.isArray(inv.studies)) {
      errors.push(`investigations[${i}]: needs an id, a title and a list of studies`); return;
    }
    checkId(inv.id, "investigation", errors);
    inv.studies.forEach((s, j) => {
      if (!isObj(s) || !isStr(s.id) || !isStr(s.title) || !Array.isArray(s.assays)) {
        errors.push(`investigation ${inv.id} studies[${j}]: needs an id, a title and a list of assays`); return;
      }
      checkId(s.id, "study", errors);
      s.assays.forEach((a, k) => checkAssay(a, `study ${s.id} assays[${k}]`, errors));
    });
  });
}

function checkReferences(project: IsaProject, catalogue: Catalogue, errors: string[]) {
  const studies = project.investigations.flatMap(i => i.studies);
  const seen = new Set<string>();
  for (const a of studies.flatMap(s => s.assays)) {
    if (seen.has(a.id)) errors.push(`duplicate assay id ${a.id}`);
    seen.add(a.id);
  }
  for (const study of studies) {
    for (const a of study.assays) {
      if (a.workflowId && !catalogue.workflows.some(w => w.id === a.workflowId))
        errors.push(`assay ${a.id}: unknown workflow ${a.workflowId}`);
      for (const { port, source } of a.inputs) {
        if (source?.kind === "existing" && !catalogue.datasets.some(d => d.id === source.datasetId))
          errors.push(`assay ${a.id} input ${port}: unknown dataset ${source.datasetId}`);
        if (source?.kind !== "planned") continue;
        const producer = study.assays.find(p => p.id === source.assayId);
        if (!producer) {
          errors.push(seen.has(source.assayId)
            ? `assay ${a.id} input ${port}: planned dataset from ${source.assayId} must come from an assay in the same study`
            : `assay ${a.id} input ${port}: unknown assay ${source.assayId}`);
        } else if (!producer.outputs.some(o => o.port === source.port)) {
          errors.push(`assay ${a.id} input ${port}: ${producer.id} has no output ${source.port}`);
        }
      }
    }
    const { cycle } = runOrder(study);
    if (cycle.length) errors.push(`study ${study.id}: assays ${cycle.join(", ")} are in or wait on a cycle`);
  }
}

/** Check an uploaded ISA project against the draft schema and the platform catalogue. */
export function validateIsaProject(json: unknown, catalogue: Catalogue): Validation {
  if (!isObj(json) || json.schemaVersion !== SCHEMA_VERSION)
    return { ok: false, errors: [`schemaVersion must be "${SCHEMA_VERSION}"`] };
  const errors: string[] = [];
  checkShape(json, errors);
  if (errors.length) return { ok: false, errors };
  const project = json as unknown as IsaProject;
  checkReferences(project, catalogue, errors);
  return errors.length ? { ok: false, errors } : { ok: true, project };
}

// ---- Dependencies and status --------------------------------------------------------------

/** Assay ids in an order where every producer comes before its consumers. Assays that are in,
 *  or wait on, a cycle are left out of `order` and listed in `cycle`. */
export function runOrder(study: Study): { order: string[]; cycle: string[] } {
  const known = new Set(study.assays.map(a => a.id));
  const pending = new Map<string, Set<string>>();
  for (const a of study.assays) {
    const deps = pending.get(a.id) ?? new Set<string>();
    producers(a).filter(p => known.has(p)).forEach(p => deps.add(p));
    pending.set(a.id, deps);
  }
  const order: string[] = [];
  let progressed = true;
  while (progressed) {
    progressed = false;
    for (const [id, deps] of pending) {
      if ([...deps].every(d => order.includes(d))) {
        order.push(id);
        pending.delete(id);
        progressed = true;
      }
    }
  }
  return { order, cycle: [...pending.keys()] };
}

function downstreamOf(study: Study, assayId: string): Set<string> {
  const out = new Set<string>();
  const visit = (id: string) => {
    for (const a of study.assays) {
      if (!out.has(a.id) && producers(a).includes(id)) { out.add(a.id); visit(a.id); }
    }
  };
  visit(assayId);
  return out;
}

export function assayStatus(study: Study, sim: Sim, assayId: string): AssayStatus {
  if (sim.submitted.includes(assayId)) return "submitted";
  if (sim.ran.includes(assayId)) return "ran";
  const a = study.assays.find(x => x.id === assayId);
  if (!a || !a.workflowId || a.inputs.some(i => !i.source)) return "unconfigured";
  return producers(a).every(p => sim.submitted.includes(p)) ? "ready" : "blocked";
}

/** One simulated wave: every ready assay runs and its outputs are submitted. */
export function simulateRunStep(study: Study, sim: Sim): { sim: Sim; ran: string[] } {
  const ran = runOrder(study).order.filter(id => assayStatus(study, sim, id) === "ready");
  return { sim: { ran: sim.ran, submitted: [...sim.submitted, ...ran] }, ran };
}

/** Run one assay (simulated), if it is ready. Its outputs aren't submitted yet. */
export function simulateLaunch(study: Study, sim: Sim, assayId: string): Sim {
  return assayStatus(study, sim, assayId) === "ready" ? { ...sim, ran: [...sim.ran, assayId] } : sim;
}

/** Submit the outputs of an assay that has run, so its planned datasets now exist. */
export function simulateSubmit(sim: Sim, assayId: string): Sim {
  if (!sim.ran.includes(assayId)) return sim;
  return { ran: sim.ran.filter(id => id !== assayId), submitted: [...sim.submitted, assayId] };
}

/** Per-subject (measurements) inputs whose producer runs fewer subjects than this assay, so part
 *  of this assay's cohort will have no data. An empty cohort means every subject. */
export function cohortWarnings(study: Study, assayId: string) {
  const a = study.assays.find(x => x.id === assayId);
  if (!a) return [];
  return a.inputs.flatMap(({ port, source }) => {
    if (source?.kind !== "planned") return [];
    const producer = study.assays.find(x => x.id === source.assayId);
    const output = producer?.outputs.find(o => o.port === source.port);
    if (!producer || !output || output.category !== "measurements" || !producer.cohort.length) return [];
    const covered = new Set(producer.cohort);
    const uncovered = !a.cohort.length || a.cohort.some(n => !covered.has(n));
    return uncovered
      ? [{ port, datasetName: output.datasetName, producerTitle: producer.title, subjects: formatCohort(producer.cohort) }]
      : [];
  });
}

export const cohortWarningText = (w: { datasetName: string; subjects: string }) =>
  `${w.datasetName} will only cover subjects ${w.subjects}.`;

// ---- Configuration ------------------------------------------------------------------------

/** What an input of `category` on `assayId` can read: existing datasets, and the planned datasets
 *  of other assays in the study, except those downstream of this one (that would be a cycle). */
export function inputOptions(study: Study, catalogue: Catalogue, assayId: string, category: Category): InputOption[] {
  const excluded = downstreamOf(study, assayId).add(assayId);
  const existing: InputOption[] = catalogue.datasets
    .filter(d => d.category === category)
    .map(d => ({ key: `existing:${d.id}`, label: d.name, planned: false, ...(d.bundled ? { bundled: true as const } : {}),
      source: { kind: "existing", datasetId: d.id } }));
  const planned: InputOption[] = study.assays
    .filter(a => !excluded.has(a.id))
    .flatMap(a => a.outputs.filter(o => o.category === category).map(o => ({
      key: `planned:${a.id}:${o.port}`, label: plannedLabel(o.datasetName, o.port), planned: true, producedBy: a.title,
      source: { kind: "planned", assayId: a.id, port: o.port } as InputSource,
    })));
  return [...existing, ...planned];
}

/** Point an assay at a workflow: its ports become the assay's inputs and outputs, and any input
 *  elsewhere in the study that read an output the assay no longer has is cleared. */
export function setWorkflow(study: Study, assayId: string, wf: CatalogueWorkflow): void {
  const a = study.assays.find(x => x.id === assayId);
  if (!a) return;
  a.workflowId = wf.id;
  a.inputs = wf.inputs.map(p => ({ port: p.name, source: null }));
  // Like the platform, one dataset holds every output until the user splits them.
  a.outputs = wf.outputs.map(p => ({ port: p.name, datasetName: `${a.title} outputs`, category: p.category }));
  const ports = new Set(a.outputs.map(o => o.port));
  for (const other of study.assays) {
    for (const i of other.inputs) {
      if (i.source?.kind === "planned" && i.source.assayId === assayId && !ports.has(i.source.port)) i.source = null;
    }
  }
}

/** Inputs of one assay that read the same dataset. `producer` is set when that dataset is planned. */
export interface InputGroup {
  key: string;
  title: string;
  producer: { id: string; title: string } | null;
  ports: string[];
}

/** An assay's inputs grouped by where they read from: one group per planned dataset or platform
 *  dataset, in the order the inputs first use it, then the inputs with no source yet. */
export function inputGroups(study: Study, catalogue: Catalogue, assayId: string): InputGroup[] {
  const groups = new Map<string, InputGroup>();
  const none: InputGroup = { key: "none", title: "Not chosen yet", producer: null, ports: [] };
  for (const { port, source } of study.assays.find(a => a.id === assayId)?.inputs ?? []) {
    if (!source) { none.ports.push(port); continue; }
    let group: InputGroup;
    if (source.kind === "existing") {
      const name = catalogue.datasets.find(d => d.id === source.datasetId)?.name ?? source.datasetId;
      group = { key: `existing:${source.datasetId}`, title: name, producer: null, ports: [] };
    } else {
      const producer = study.assays.find(a => a.id === source.assayId);
      const name = producer?.outputs.find(o => o.port === source.port)?.datasetName ?? source.port;
      group = { key: `planned:${source.assayId}:${name}`, title: name,
        producer: { id: source.assayId, title: producer?.title ?? source.assayId }, ports: [] };
    }
    if (!groups.has(group.key)) groups.set(group.key, group);
    groups.get(group.key)!.ports.push(port);
  }
  return [...groups.values(), ...(none.ports.length ? [none] : [])];
}

/** An assay's outputs grouped by the dataset they fill, in order. */
export function outputGroups(assay: Assay): { datasetName: string; ports: AssayOutput[] }[] {
  const groups = new Map<string, AssayOutput[]>();
  for (const o of assay.outputs) groups.set(o.datasetName, [...(groups.get(o.datasetName) ?? []), o]);
  return [...groups].map(([datasetName, ports]) => ({ datasetName, ports }));
}

export function workflowTools(catalogue: Catalogue, workflowId: string | null) {
  const wf = catalogue.workflows.find(w => w.id === workflowId);
  return (wf?.steps ?? []).map(step => {
    const tool = catalogue.tools.find(t => t.id === step.toolId);
    return tool
      ? { stepId: step.id, toolName: tool.name, toolType: tool.type }
      : { stepId: step.id, toolName: `${step.toolId} (not in catalogue)`, toolType: null };
  });
}

// ---- Study graph --------------------------------------------------------------------------

/** Nodes and edges for one study, in columns: one per assay level, with each platform dataset the
 *  study reads in the column before its first reader. Edges between assays carry planned datasets,
 *  planned until their producer has submitted; a platform dataset's edge counts the inputs it feeds. */
export function studyGraph(study: Study, catalogue: Catalogue, sim: Sim) {
  const level = new Map<string, number>();
  for (const id of runOrder(study).order) {
    const a = study.assays.find(x => x.id === id)!;
    level.set(id, Math.max(-1, ...producers(a).map(p => level.get(p) ?? -1)) + 1);
  }
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();
  const rows = new Map<number, number>();
  const addNode = (n: Omit<GraphNode, "row">) => {
    if (nodes.has(n.id)) return;
    const row = rows.get(n.column) ?? 0;
    rows.set(n.column, row + 1);
    nodes.set(n.id, { ...n, row });
  };

  const column = (a: Assay) => (level.get(a.id) ?? 0) + 1;
  for (const a of study.assays) {
    addNode({ id: `assay:${a.id}`, kind: "assay", label: a.title, column: column(a),
      status: assayStatus(study, sim, a.id), assayId: a.id });
  }
  // A platform dataset sits just before the first assay that reads it, not always in column 0, so
  // a dataset read only late in the study doesn't send a long edge across the earlier assays.
  const sourceColumn = new Map<string, number>();
  for (const a of study.assays) {
    for (const { source } of a.inputs) {
      if (source?.kind !== "existing") continue;
      const key = sourceKey(source);
      sourceColumn.set(key, Math.min(sourceColumn.get(key) ?? Infinity, column(a) - 1));
    }
  }
  const sourceReads = new Map<string, number>();
  for (const a of study.assays) {
    for (const { source } of a.inputs) {
      if (!source) continue;
      let from: string;
      let label: string | null = null;
      if (source.kind === "existing") {
        from = sourceKey(source);
        const ds = catalogue.datasets.find(d => d.id === source.datasetId);
        addNode({ id: from, kind: "source", label: ds?.name ?? source.datasetId, column: sourceColumn.get(from)!,
          ...(ds?.bundled ? { bundled: true as const } : {}) });
      } else {
        from = `assay:${source.assayId}`;
        if (!nodes.has(from)) continue;
        const name = study.assays.find(x => x.id === source.assayId)?.outputs
          .find(o => o.port === source.port)?.datasetName;
        label = name ? plannedLabel(name, source.port) : source.port;
      }
      const id = `${from}->assay:${a.id}`;
      const edge = edges.get(id) ?? { id, source: from, target: `assay:${a.id}`, labels: [], planned: false };
      if (label && !edge.labels.includes(label)) edge.labels.push(label);
      if (source.kind === "planned" && !sim.submitted.includes(source.assayId)) edge.planned = true;
      if (source.kind === "existing") sourceReads.set(id, (sourceReads.get(id) ?? 0) + 1);
      edges.set(id, edge);
    }
  }
  for (const [id, n] of sourceReads) if (n > 1) edges.get(id)!.labels = [`${n} inputs`];
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

// ---- Cohort -------------------------------------------------------------------------------

/** "1-3,5" -> [1,2,3,5]; "" -> [] (every subject); null when the text isn't a range list. */
export function parseCohort(text: string): number[] | null {
  const out = new Set<number>();
  for (const part of text.split(",").map(s => s.trim()).filter(Boolean)) {
    const m = /^(\d+)(?:\s*-\s*(\d+))?$/.exec(part);
    if (!m) return null;
    const start = Number(m[1]);
    const end = m[2] ? Number(m[2]) : start;
    if (start < 1 || end < start) return null;
    for (let n = start; n <= end; n++) out.add(n);
  }
  return [...out].sort((x, y) => x - y);
}

export function formatCohort(nums: number[]): string {
  const sorted = [...new Set(nums)].sort((x, y) => x - y);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; i++) {
    const start = sorted[i];
    while (sorted[i + 1] === sorted[i] + 1) i++;
    parts.push(start === sorted[i] ? `${start}` : `${start}-${sorted[i]}`);
  }
  return parts.join(",");
}
