import { describe, expect, it } from "vitest";
import type { Assay, Catalogue, IsaProject, Study } from "../model/types";
import {
  assayStatus,
  cohortWarnings,
  formatCohort,
  inputOptions,
  parseCohort,
  runOrder,
  setWorkflow,
  simulateLaunch,
  simulateRunStep,
  simulateSubmit,
  studyGraph,
  validateIsaProject,
  workflowTools,
} from "../model/isaProject";

const catalogue: Catalogue = {
  tools: [
    { id: "t-seg", name: "Lung segmenter", type: "script" },
    { id: "t-mesh", name: "Mesher", type: "script" },
  ],
  workflows: [
    {
      id: "wf-seg", name: "Segment", type: "script",
      inputs: [{ name: "ct", category: "measurements" }],
      outputs: [{ name: "masks", category: "measurements" }],
      steps: [{ id: "segment", toolId: "t-seg" }], cwl: {},
    },
    {
      id: "wf-mesh", name: "Mesh", type: "script",
      inputs: [{ name: "masks", category: "measurements" }],
      outputs: [{ name: "meshes", category: "models" }, { name: "report", category: "measurements" }],
      steps: [{ id: "mesh", toolId: "t-mesh" }, { id: "qa", toolId: "t-missing" }], cwl: {},
    },
  ],
  datasets: [
    { id: "ds-ct", name: "Chest CT", category: "measurements" },
    { id: "ds-model", name: "Template", category: "models" },
  ],
};

const assay = (id: string, over: Partial<Assay> = {}): Assay => ({
  id, title: id.toUpperCase(), type: "script", workflowId: null, cohort: [], inputs: [], outputs: [], ...over,
});

// a1 (segment) -> a2 (mesh) -> a3 (consumes a2's report)
const chain = (): Study => ({
  id: "s1", title: "Study 1",
  assays: [
    assay("a1", {
      workflowId: "wf-seg",
      inputs: [{ port: "ct", source: { kind: "existing", datasetId: "ds-ct" } }],
      outputs: [{ port: "masks", datasetName: "Lung masks", category: "measurements" }],
    }),
    assay("a2", {
      workflowId: "wf-mesh",
      inputs: [{ port: "masks", source: { kind: "planned", assayId: "a1", port: "masks" } }],
      outputs: [
        { port: "meshes", datasetName: "Lung meshes", category: "models" },
        { port: "report", datasetName: "Mesh report", category: "measurements" },
      ],
    }),
    assay("a3", {
      workflowId: "wf-mesh",
      inputs: [{ port: "masks", source: { kind: "planned", assayId: "a2", port: "report" } }],
      outputs: [{ port: "meshes", datasetName: "Other meshes", category: "models" }],
    }),
  ],
});

const project = (studies: Study[]): IsaProject => ({
  schemaVersion: "0.1-draft",
  project: { id: "p1", title: "Project" },
  investigations: [{ id: "i1", title: "Inv", studies }],
});

describe("validateIsaProject", () => {
  it("accepts a well-formed project", () => {
    expect(validateIsaProject(project([chain()]), catalogue)).toEqual({ ok: true, project: project([chain()]) });
  });

  it("rejects something that isn't a draft ISA project", () => {
    const r = validateIsaProject({ schemaVersion: "9" }, catalogue);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors[0]).toMatch(/schemaVersion/);
  });

  it("rejects a planned input from another study", () => {
    const other: Study = { id: "s2", title: "S2", assays: [assay("b1", {
      inputs: [{ port: "masks", source: { kind: "planned", assayId: "a1", port: "masks" } }],
    })] };
    const r = validateIsaProject(project([chain(), other]), catalogue);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.join()).toMatch(/b1.*a1.*same study/);
  });

  it("rejects a planned input naming an output its producer doesn't declare", () => {
    const s = chain();
    s.assays[1].inputs[0].source = { kind: "planned", assayId: "a1", port: "nope" };
    const r = validateIsaProject(project([s]), catalogue);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.join()).toMatch(/nope/);
  });

  it("rejects ids that can't be used in a dashboard link", () => {
    const s = chain();
    s.id = "s,1";
    s.assays[0].id = "a:1";
    const r = validateIsaProject(project([s]), catalogue);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.filter(e => /letters, digits/.test(e))).toHaveLength(2);
  });

  it("rejects an unknown workflow, a duplicate assay id and a cycle", () => {
    const s = chain();
    s.assays[0].workflowId = "wf-ghost";
    s.assays[0].inputs[0].source = { kind: "planned", assayId: "a3", port: "meshes" };
    s.assays.push(assay("a2"));
    const r = validateIsaProject(project([s]), catalogue);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      const all = r.errors.join("\n");
      expect(all).toMatch(/wf-ghost/);
      expect(all).toMatch(/duplicate.*a2/i);
      expect(all).toMatch(/cycle/i);
    }
  });
});

describe("inputOptions", () => {
  it("offers existing datasets and upstream planned datasets of the input's category", () => {
    const opts = inputOptions(chain(), catalogue, "a2", "measurements");
    expect(opts).toEqual([
      { key: "existing:ds-ct", label: "Chest CT", planned: false, source: { kind: "existing", datasetId: "ds-ct" } },
      { key: "planned:a1:masks", label: "Lung masks", planned: true, producedBy: "A1",
        source: { kind: "planned", assayId: "a1", port: "masks" } },
    ]);
  });

  it("never offers the assay's own outputs or those of assays downstream of it", () => {
    const keys = inputOptions(chain(), catalogue, "a1", "measurements").map(o => o.key);
    expect(keys).toEqual(["existing:ds-ct"]); // a2.report and a3 are downstream of a1
  });

  it("filters by category", () => {
    const keys = inputOptions(chain(), catalogue, "a3", "models").map(o => o.key);
    expect(keys).toEqual(["existing:ds-model", "planned:a2:meshes"]);
  });
});

describe("runOrder", () => {
  it("orders assays so producers run before consumers", () => {
    const s = chain();
    s.assays.reverse();
    expect(runOrder(s)).toEqual({ order: ["a1", "a2", "a3"], cycle: [] });
  });

  it("reports the assays caught in a cycle", () => {
    const s = chain();
    s.assays[0].inputs[0].source = { kind: "planned", assayId: "a3", port: "meshes" };
    expect(runOrder(s).cycle.sort()).toEqual(["a1", "a2", "a3"]);
  });
});

const sim = (ran: string[] = [], submitted: string[] = []) => ({ ran, submitted });

describe("assayStatus and simulateRunStep", () => {
  it("marks unconfigured, ready, blocked, run and submitted assays", () => {
    const s = chain();
    s.assays.push(assay("a4", { workflowId: "wf-seg", inputs: [{ port: "ct", source: null }] }));
    s.assays.push(assay("a5"));
    expect(s.assays.map(a => assayStatus(s, sim(), a.id)))
      .toEqual(["ready", "blocked", "blocked", "unconfigured", "unconfigured"]);
    expect(assayStatus(s, sim(["a1"]), "a1")).toBe("ran");
    expect(assayStatus(s, sim([], ["a1"]), "a1")).toBe("submitted");
  });

  it("keeps a consumer waiting until its producer's outputs are submitted, not just run", () => {
    const s = chain();
    expect(assayStatus(s, sim(["a1"]), "a2")).toBe("blocked");
    expect(assayStatus(s, sim([], ["a1"]), "a2")).toBe("ready");
  });

  it("runs and submits one wave of ready assays per step, in dependency order", () => {
    const s = chain();
    expect(simulateRunStep(s, sim())).toEqual({ sim: sim([], ["a1"]), ran: ["a1"] });
    expect(simulateRunStep(s, sim([], ["a1"]))).toEqual({ sim: sim([], ["a1", "a2"]), ran: ["a2"] });
    expect(simulateRunStep(s, sim([], ["a1", "a2", "a3"]))).toEqual({ sim: sim([], ["a1", "a2", "a3"]), ran: [] });
  });
});

describe("simulateLaunch and simulateSubmit", () => {
  it("launches only a ready assay, and submits only one that has run", () => {
    const s = chain();
    expect(simulateLaunch(s, sim(), "a2")).toEqual(sim());
    expect(simulateLaunch(s, sim(), "a1")).toEqual(sim(["a1"]));
    expect(simulateSubmit(sim(), "a1")).toEqual(sim());
    expect(simulateSubmit(sim(["a1"]), "a1")).toEqual(sim([], ["a1"]));
  });
});

describe("cohortWarnings", () => {
  it("warns when an assay reads per-subject data for subjects its producer doesn't run", () => {
    const s = chain();
    s.assays[0].cohort = [1, 2, 3];
    expect(cohortWarnings(s, "a2")).toEqual([
      { port: "masks", datasetName: "Lung masks", producerTitle: "A1", subjects: "1-3" },
    ]);
    s.assays[1].cohort = [2, 3];
    expect(cohortWarnings(s, "a2")).toEqual([]);
  });

  it("never warns when the producer runs every subject, or the data is a model", () => {
    const s = chain();
    expect(cohortWarnings(s, "a2")).toEqual([]);
    s.assays[1].cohort = [1];
    s.assays[2].inputs.push({ port: "extra", source: { kind: "planned", assayId: "a2", port: "meshes" } });
    expect(cohortWarnings(s, "a3").map(w => w.port)).toEqual(["masks"]); // a2's report, not its meshes
  });
});

describe("setWorkflow", () => {
  it("replaces the assay's ports with the workflow's and clears inputs that pointed at removed outputs", () => {
    const s = chain();
    setWorkflow(s, "a2", catalogue.workflows[0]); // wf-seg: out "masks" only, so a3's "report" link breaks
    expect(s.assays[1].workflowId).toBe("wf-seg");
    expect(s.assays[1].inputs).toEqual([{ port: "ct", source: null }]);
    expect(s.assays[1].outputs).toEqual([{ port: "masks", datasetName: "A2 masks", category: "measurements" }]);
    expect(s.assays[2].inputs[0].source).toBeNull();
  });
});

describe("workflowTools", () => {
  it("lists each step with its tool, or a placeholder for an unknown tool", () => {
    expect(workflowTools(catalogue, "wf-mesh")).toEqual([
      { stepId: "mesh", toolName: "Mesher", toolType: "script" },
      { stepId: "qa", toolName: "t-missing (not in catalogue)", toolType: null },
    ]);
    expect(workflowTools(catalogue, null)).toEqual([]);
  });
});

describe("studyGraph", () => {
  it("places assays by level, fed by the datasets already on the platform", () => {
    const g = studyGraph(chain(), catalogue, sim());
    const node = (id: string) => g.nodes.find(n => n.id === id)!;
    expect(node("existing:ds-ct")).toMatchObject({ kind: "source", label: "Chest CT", column: 0, row: 0 });
    expect(node("assay:a1")).toMatchObject({ kind: "assay", label: "A1", column: 1, status: "ready", assayId: "a1" });
    expect(node("assay:a2")).toMatchObject({ column: 2, status: "blocked" });
    expect(node("assay:a3")).toMatchObject({ column: 3 });
    expect(g.nodes.map(n => n.kind)).toEqual(["assay", "assay", "assay", "source"]);
  });

  it("joins assays with one edge each, labelled with the datasets it carries and planned until they are submitted", () => {
    const s = chain();
    s.assays[2].inputs.push({ port: "extra", source: { kind: "planned", assayId: "a2", port: "meshes" } });
    const g = studyGraph(s, catalogue, sim());
    expect(g.edges).toEqual([
      { id: "existing:ds-ct->assay:a1", source: "existing:ds-ct", target: "assay:a1", labels: [], planned: false },
      { id: "assay:a1->assay:a2", source: "assay:a1", target: "assay:a2", labels: ["Lung masks"], planned: true },
      { id: "assay:a2->assay:a3", source: "assay:a2", target: "assay:a3", labels: ["Mesh report", "Lung meshes"], planned: true },
    ]);
    expect(studyGraph(s, catalogue, sim(["a1"])).edges.find(e => e.id === "assay:a1->assay:a2")!.planned).toBe(true);
    expect(studyGraph(s, catalogue, sim([], ["a1"])).edges.find(e => e.id === "assay:a1->assay:a2")!.planned).toBe(false);
  });
});

describe("cohort", () => {
  it("parses and formats subject ranges", () => {
    expect(parseCohort("1-3, 5,9-10")).toEqual([1, 2, 3, 5, 9, 10]);
    expect(parseCohort("")).toEqual([]);
    expect(parseCohort("1-x")).toBeNull();
    expect(formatCohort([5, 1, 2, 3, 9, 10])).toBe("1-3,5,9-10");
  });
});
