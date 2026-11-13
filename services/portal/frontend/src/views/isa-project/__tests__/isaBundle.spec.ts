import { describe, expect, it } from "vitest";
import JSZip from "jszip";
import { bundleFiles, bundleManifest, readBundle, withBundled, type BundleFile } from "../adapter/isaBundle";
import { fixtureSource } from "../adapter/isaProjectSource";
import type { IsaProject } from "../model/types";

// A bundle as path -> text; the size of each file is its text length.
const files = (tree: Record<string, string>): BundleFile[] =>
  Object.entries(tree).map(([path, text]) => ({ path, size: text.length, text: async () => text }));

const WORKFLOW_CWL = `cwlVersion: v1.2
class: Workflow
inputs:
  scans:
    type: Directory
    doc: measurements
outputs:
  masks:
    type: Directory
    outputSource: segment/masks
    doc: models
steps:
  segment:
    run: tool_seg_unet.cwl
    in: { scans: scans }
    out: [masks]
  convert:
    run: tool_dicom_to_nrrd.cwl
    in: { scans: scans }
    out: [nrrd]
`;

/** One study: a new workflow (wf-seg) reads a new dataset (ds-scans); a platform workflow reads a
 *  platform dataset. */
function design(over: Partial<{ datasetId: string; workflowId: string }> = {}): IsaProject {
  return {
    schemaVersion: "0.1-draft",
    project: { id: "p-new", title: "New study plan" },
    investigations: [{ id: "i", title: "I", studies: [{ id: "s", title: "S", assays: [
      { id: "a-seg", title: "Segment scans", type: "script", workflowId: over.workflowId ?? "wf-seg", cohort: [],
        inputs: [{ port: "scans", source: { kind: "existing", datasetId: over.datasetId ?? "ds-scans" } }],
        outputs: [{ port: "masks", datasetName: "masks", category: "models" }] },
      { id: "a-cohort", title: "Curate", type: "notebook", workflowId: "wf-mri-curation", cohort: [],
        inputs: [{ port: "raw_dataset", source: { kind: "existing", datasetId: "ds-test-dicom" } }],
        outputs: [{ port: "curated_dataset", datasetName: "curated", category: "measurements" }] },
    ] }] }],
  };
}

const bundle = (project: unknown = design(), extra: Record<string, string> = {}) => files({
  "isa-project.json": JSON.stringify(project),
  "datasets/ds-scans/dataset_description.xlsx": "",
  "datasets/ds-scans/primary/sub-1/scan.dcm": "x".repeat(100),
  "datasets/ds-scans/primary/sub-2/scan.dcm": "x".repeat(50),
  "datasets/wf-seg/dataset_description.xlsx": "",
  "datasets/wf-seg/primary/workflow_seg.cwl": WORKFLOW_CWL,
  "datasets/wf-seg/primary/tool_seg_unet.cwl": "class: CommandLineTool",
  "datasets/wf-seg/primary/tool_dicom_to_nrrd.cwl": "class: CommandLineTool",
  ...extra,
});

const read = async (f: BundleFile[]) => readBundle(f, await fixtureSource.catalogue());

describe("readBundle", () => {
  it("adds the design with the datasets and workflows that aren't on the platform yet", async () => {
    const r = await read(bundle());
    expect(r.errors).toEqual([]);
    expect(r.warnings).toEqual([]);
    expect(r.project?.project.id).toBe("p-new");
    expect(r.bundled.datasets).toEqual([
      { id: "ds-scans", name: "ds-scans", category: "measurements", bundled: { fileCount: 3, bytes: 150 } },
    ]);
  });

  it("reads a new workflow's ports, categories and steps from its CWL", async () => {
    const { bundled } = await read(bundle());
    const wf = bundled.workflows[0];
    expect(wf).toMatchObject({
      id: "wf-seg", name: "workflow_seg", type: "script",
      inputs: [{ name: "scans", category: "measurements" }],
      outputs: [{ name: "masks", category: "models" }],
    });
    expect(wf.bundled?.fileCount).toBe(4);
    expect(wf.cwl).toMatchObject({ class: "Workflow" });
  });

  it("reuses a tool the platform has, and adds the package's other tools", async () => {
    const { bundled } = await read(bundle());
    expect(bundled.workflows[0].steps).toEqual([
      { id: "segment", toolId: "tool_seg_unet" },
      { id: "convert", toolId: "t-dicom-to-nrrd" },
    ]);
    expect(bundled.tools).toEqual([{ id: "tool_seg_unet", name: "tool_seg_unet", type: "script", bundled: { fileCount: 1, bytes: 22 } }]);
  });

  it("takes a step's tool from a tool package in the bundle", async () => {
    const f = bundle(design(), {
      "datasets/t-unet/dataset_description.xlsx": "",
      "datasets/t-unet/primary/tool_seg_unet.cwl": "class: CommandLineTool",
    })
      .filter(x => x.path !== "datasets/wf-seg/primary/tool_seg_unet.cwl");
    const r = await read(f);
    expect(r.errors).toEqual([]);
    expect(r.bundled.workflows[0].steps[0]).toEqual({ id: "segment", toolId: "t-unet" });
    expect(r.bundled.tools.map(t => [t.id, t.name])).toEqual([["t-unet", "tool_seg_unet"]]);
    expect(r.bundled.tools[0].bundled?.fileCount).toBe(2);
  });

  it("takes a new dataset's category from the workflow port that reads it", async () => {
    const wf = WORKFLOW_CWL.replace("doc: measurements", "doc: models");
    const { bundled } = await read(bundle(design(), { "datasets/wf-seg/primary/workflow_seg.cwl": wf }));
    expect(bundled.datasets[0].category).toBe("models");
  });

  it("peels off a single wrapper folder, as a zipped folder has", async () => {
    const wrapped = bundle().map(f => ({ ...f, path: `my-project/${f.path}` }));
    expect((await read(wrapped)).errors).toEqual([]);
  });

  it("needs exactly one JSON file at the bundle root", async () => {
    const none = bundle().filter(f => f.path !== "isa-project.json");
    expect((await read(none)).errors).toEqual(["The bundle needs one .json file at its root, the ISA project; it has none."]);
    const two = bundle(design(), { "notes.json": "{}" });
    expect((await read(two)).errors).toEqual(["The bundle needs one .json file at its root, the ISA project; it has 2: isa-project.json, notes.json."]);
  });

  it("says which folder a new id is missing", async () => {
    const r = await read(bundle(design({ datasetId: "ds-raw" })));
    expect(r.project).toBeNull();
    expect(r.errors).toContain("assay a-seg input scans: unknown dataset ds-raw (no datasets/ds-raw/ folder in the bundle)");
  });

  it("says when a folder is the wrong kind for what the design uses it as", async () => {
    const r = await read(bundle(design({ workflowId: "ds-scans", datasetId: "wf-seg" })));
    expect(r.errors).toContain("assay a-seg: unknown workflow ds-scans (datasets/ds-scans/ has no primary/workflow_*.cwl)");
    expect(r.errors).toContain("assay a-seg input scans: unknown dataset wf-seg (datasets/wf-seg/ is a workflow package, not a dataset)");
  });

  it("rejects a workflow package without exactly one workflow CWL, or missing a step's tool", async () => {
    const two = await read(bundle(design(), { "datasets/wf-seg/primary/workflow_other.cwl": WORKFLOW_CWL }));
    expect(two.errors).toContain("datasets/wf-seg/: a workflow package needs exactly one primary/workflow_*.cwl; it has 2.");
    const noTool = await read(bundle().filter(f => f.path !== "datasets/wf-seg/primary/tool_seg_unet.cwl"));
    expect(noTool.errors).toContain("datasets/wf-seg/: step segment runs tool_seg_unet.cwl, which is neither in primary/, in a tool package in the bundle, nor on the platform.");
  });

  it("needs every folder the design uses to be an SDS package", async () => {
    const noMarker = (folder: string) => bundle().filter(f => f.path !== `datasets/${folder}/dataset_description.xlsx`);
    expect((await read(noMarker("ds-scans"))).errors)
      .toEqual(["datasets/ds-scans/ isn't an SDS package: it needs dataset_description.xlsx at its root."]);
    expect((await read(noMarker("wf-seg"))).errors)
      .toEqual(["datasets/wf-seg/ isn't an SDS package: it needs dataset_description.xlsx at its root."]);
  });

  it("needs a dataset's files under primary/", async () => {
    const flat = bundle().filter(f => !f.path.startsWith("datasets/ds-scans/primary/"))
      .concat(files({ "datasets/ds-scans/scan.dcm": "x" }));
    expect((await read(flat)).errors).toEqual(["datasets/ds-scans/ has no files under primary/."]);
  });

  it("gives a bundled dataset one category, so inputs of two categories can't both read it", async () => {
    const p = design();
    p.investigations[0].studies[0].assays[1].inputs[0].source = { kind: "existing", datasetId: "ds-scans" };
    const wf = WORKFLOW_CWL.replace("doc: measurements", "doc: models");
    const r = await read(bundle(p, { "datasets/wf-seg/primary/workflow_seg.cwl": wf }));
    expect(r.errors).toEqual(["datasets/ds-scans/ is read as models by assay a-seg input scans and as measurements " +
      "by assay a-cohort input raw_dataset; a dataset has one category."]);
  });

  it("reports CWL that can't be read", async () => {
    const r = await read(bundle(design(), { "datasets/wf-seg/primary/workflow_seg.cwl": "inputs: [unclosed" }));
    expect(r.errors[0]).toMatch(/^datasets\/wf-seg\/primary\/workflow_seg\.cwl can't be read:/);
  });

  it("warns about folders the design doesn't use, and leaves them out", async () => {
    const r = await read(bundle(design(), {
      "datasets/old-scratch/a.txt": "a",
      "datasets/ds-test-dicom/b.txt": "b",
    }));
    expect(r.errors).toEqual([]);
    expect(r.warnings).toEqual([
      "datasets/old-scratch/ isn't used by the design, so it is left out.",
      "datasets/ds-test-dicom/ is already on the platform; the design uses the platform's copy, so this folder is left out.",
    ]);
    expect(r.bundled.datasets.map(d => d.id)).toEqual(["ds-scans"]);
  });

  it("reports a JSON file that isn't valid JSON", async () => {
    const f = bundle().map(x => (x.path === "isa-project.json" ? { ...x, text: async () => "{nope" } : x));
    expect((await read(f)).errors).toEqual(["isa-project.json is not valid JSON."]);
  });
});

describe("withBundled", () => {
  it("adds a bundle's items to the platform catalogue", async () => {
    const catalogue = await fixtureSource.catalogue();
    const { bundled } = await read(bundle());
    const merged = withBundled(catalogue, bundled);
    expect(merged.datasets).toHaveLength(catalogue.datasets.length + 1);
    expect(merged.workflows.at(-1)?.id).toBe("wf-seg");
    expect(withBundled(catalogue, undefined)).toEqual(catalogue);
  });
});

describe("bundleManifest", () => {
  it("lists what the bundle adds, who uses it, and how much is already on the platform", async () => {
    const catalogue = await fixtureSource.catalogue();
    const { project, bundled } = await read(bundle());
    const m = bundleManifest(project!, bundled, catalogue);
    expect(m.rows).toEqual([
      { kind: "dataset", id: "ds-scans", name: "ds-scans", meta: "measurements, 3 files, 150 B", usedBy: ["Segment scans"] },
      { kind: "workflow", id: "wf-seg", name: "workflow_seg", meta: "script, 2 steps, 4 files", usedBy: ["Segment scans"] },
      { kind: "tool", id: "tool_seg_unet", name: "tool_seg_unet", meta: "script", usedBy: ["workflow_seg"] },
    ]);
    expect(m.onPlatform).toEqual({ datasets: 1, workflows: 1, tools: 1 });
  });
});

describe("bundleFiles", () => {
  it("lists a picked folder's files relative to the folder", async () => {
    const file = (path: string, text: string) =>
      Object.assign(new File([text], path.split("/").pop()!), { webkitRelativePath: path, text: async () => text });
    const list = await bundleFiles({
      kind: "folder", rootName: "my-project", fileCount: 2, totalSize: 5,
      files: [file("my-project/isa-project.json", "{}"), file("my-project/datasets/d/a.txt", "abc")],
    });
    expect(list.map(f => [f.path, f.size])).toEqual([["my-project/isa-project.json", 2], ["my-project/datasets/d/a.txt", 3]]);
    expect(await list[1].text()).toBe("abc");
  });

  it("lists a zip's files with their unpacked sizes", async () => {
    const zip = new JSZip();
    zip.file("my-project/isa-project.json", "{}");
    zip.file("my-project/datasets/d/a.txt", "abcd");
    const blob = new Blob([await zip.generateAsync({ type: "arraybuffer" })]);
    const list = await bundleFiles({ kind: "zip", blob, rootName: "my-project", fileCount: 2, totalSize: blob.size });
    expect(list.map(f => [f.path, f.size])).toEqual([["my-project/isa-project.json", 2], ["my-project/datasets/d/a.txt", 4]]);
    expect(await list[1].text()).toBe("abcd");
  });
});
