// Write an ISA project as a bundle (prototype): its JSON plus an SDS skeleton for each dataset and
// workflow it uses. The prototype holds no dataset files, so each folder gets a generated
// dataset_description.xlsx and placeholders (or the workflow's CWL) to fill in. readBundle reads it back.
import yaml from "js-yaml";
import type { Catalogue, CatalogueWorkflow, IsaProject, Port } from "../model/types";
import testProjectJson from "../fixtures/example-test-project.json";

const PLACEHOLDER = "Placeholder made by the ISA project prototype: replace it with the real one.";

type Section = Record<string, unknown> | { id?: string }[] | undefined;
/** A port's definition in a CWL `inputs` / `outputs` section, map or list form. */
const portDef = (section: Section, name: string): Record<string, unknown> => {
  const def = Array.isArray(section)
    ? section.find(p => String(p?.id).replace(/^#/, "") === name)
    : section?.[name];
  return typeof def === "object" && def !== null ? { ...(def as Record<string, unknown>) } : { type: "Directory" };
};
const ports = (section: Section, list: Port[]) =>
  Object.fromEntries(list.map(p => [p.name, { ...portDef(section, p.name), doc: p.category }]));

/** The workflow's CWL with each port's category as `doc`, so reading it back gives the same ports. */
function workflowCwl(wf: CatalogueWorkflow): string {
  const cwl = wf.cwl as Record<string, unknown>;
  return yaml.dump({
    cwlVersion: "v1.2",
    class: "Workflow",
    ...cwl,
    inputs: ports(cwl.inputs as Section, wf.inputs),
    outputs: ports(cwl.outputs as Section, wf.outputs),
  });
}

async function description(title: string, type: string): Promise<ArrayBuffer> {
  const XLSX = await import("xlsx");
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ["Metadata element", "Value"], ["Title", title], ["Type", type], ["Description", PLACEHOLDER],
  ]), "Sheet1");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

const readme = (name: string, category: string) => [
  `Put the files of ${name} (${category}) here.`,
  ...(category === "measurements" ? ["Use one folder per subject: sub-1, sub-2, and so on."] : []),
  PLACEHOLDER,
  "",
].join("\n");

const toolStub = (name: string) =>
  `# ${PLACEHOLDER}\ncwlVersion: v1.2\nclass: CommandLineTool\nlabel: ${name}\ninputs: {}\noutputs: {}\n`;

/** Hand a file to the browser to save. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** A zip of `project` with a folder for each dataset and workflow it uses, as found in `catalogue`
 *  (the platform plus any bundled items). `only: "bundled"` writes folders for bundled items only. */
export async function bundleZip(project: IsaProject, catalogue: Catalogue, opts: { only?: "bundled" } = {}): Promise<Blob> {
  const JSZip = (await import("jszip")).default;
  const zip = new JSZip();
  const root = zip.folder(project.project.id)!;
  root.file("isa-project.json", JSON.stringify(project, null, 2));
  const assays = project.investigations.flatMap(i => i.studies).flatMap(s => s.assays);
  const wanted = <T extends { id: string; bundled?: unknown }>(items: T[], ids: Set<string>) =>
    items.filter(x => ids.has(x.id) && (opts.only !== "bundled" || x.bundled));

  const datasetIds = new Set(assays.flatMap(a => a.inputs)
    .flatMap(i => (i.source?.kind === "existing" ? [i.source.datasetId] : [])));
  for (const d of wanted(catalogue.datasets, datasetIds)) {
    const folder = root.folder(`datasets/${d.id}`)!;
    folder.file("dataset_description.xlsx", await description(d.name, d.category));
    folder.file("primary/README.txt", readme(d.name, d.category));
  }

  const workflowIds = new Set(assays.flatMap(a => (a.workflowId ? [a.workflowId] : [])));
  for (const wf of wanted(catalogue.workflows, workflowIds)) {
    const folder = root.folder(`datasets/${wf.id}`)!;
    folder.file("dataset_description.xlsx", await description(wf.name, "workflows"));
    folder.file(`primary/${wf.name}.cwl`, workflowCwl(wf));
    // A bundled tool travels in its workflow's package; platform tools are found by name.
    for (const step of wf.steps) {
      const tool = catalogue.tools.find(t => t.id === step.toolId);
      if (tool?.bundled) folder.file(`primary/${tool.name}.cwl`, toolStub(tool.name));
    }
  }
  return zip.generateAsync({ type: "blob" });
}

/** An example to try the bundle upload with: the Test Project example, where assay 1 reads a bundled
 *  dataset and assay 2 runs a bundled copy of the image conversion workflow, one of whose steps runs
 *  a bundled tool. */
export function demoBundle(platform: Catalogue): { project: IsaProject; bundled: Catalogue } {
  const project = JSON.parse(JSON.stringify(testProjectJson)) as IsaProject;
  project.project = { id: "p-test-project-demo", title: "Test Project (bundled demo)" };
  const [first, second] = project.investigations[0].studies[0].assays;
  first.inputs[0].source = { kind: "existing", datasetId: "ds-demo-mri" };
  second.workflowId = "wf-demo-image-conversion";

  const source = platform.workflows.find(w => w.id === "wf-image-conversion")!;
  const cwl = JSON.parse(JSON.stringify(source.cwl)) as { steps: Record<string, { run: string }> };
  const tool = "tool_demo_dicom_to_png";
  cwl.steps.dicom_to_nrrd.run = `${tool}.cwl`;
  const stub = { fileCount: 0, bytes: 0 };
  return {
    project,
    bundled: {
      datasets: [{ id: "ds-demo-mri", name: "ds-demo-mri", category: "measurements", bundled: stub }],
      workflows: [{
        ...source, id: "wf-demo-image-conversion", name: "workflow_demo_image_conversion", cwl, bundled: stub,
        steps: source.steps.map(s => (s.id === "dicom_to_nrrd" ? { ...s, toolId: tool } : s)),
      }],
      tools: [{ id: tool, name: tool, type: "script", bundled: stub }],
    },
  };
}
