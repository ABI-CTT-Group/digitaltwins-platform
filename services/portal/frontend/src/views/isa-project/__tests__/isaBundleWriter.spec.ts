import { describe, expect, it } from "vitest";
import JSZip from "jszip";
import * as XLSX from "xlsx";
import { bundleFiles, readBundle, withBundled } from "../adapter/isaBundle";
import { bundleZip, demoBundle } from "../adapter/isaBundleWriter";
import { fixtureSource } from "../adapter/isaProjectSource";
import type { Catalogue, IsaProject } from "../model/types";

const example = () => fixtureSource.loadExample("example-test-project");
const platform = () => fixtureSource.catalogue();

/** Read a written bundle back the way the upload dialog does. */
async function readBack(blob: Blob, catalogue: Catalogue) {
  const files = await bundleFiles({ kind: "zip", blob, rootName: "", fileCount: 0, totalSize: blob.size });
  return readBundle(files, catalogue);
}
const paths = async (blob: Blob) => Object.keys((await JSZip.loadAsync(blob)).files).filter(p => !p.endsWith("/")).sort();

describe("bundleZip", () => {
  it("writes the project and an SDS skeleton for each dataset and workflow it uses", async () => {
    const list = await paths(await bundleZip(await example(), await platform()));
    expect(list).toContain("p-test-project/isa-project.json");
    expect(list).toContain("p-test-project/datasets/ds-test-dicom/dataset_description.xlsx");
    expect(list).toContain("p-test-project/datasets/ds-test-dicom/primary/README.txt");
    expect(list).toContain("p-test-project/datasets/wf-image-conversion/dataset_description.xlsx");
    expect(list).toContain("p-test-project/datasets/wf-image-conversion/primary/workflow_image_conversion.cwl");
    expect(list.filter(p => p.endsWith("dataset_description.xlsx"))).toHaveLength(3 + 4); // 3 datasets, 4 workflows
  });

  it("describes each dataset in its dataset_description.xlsx", async () => {
    const zip = await JSZip.loadAsync(await bundleZip(await example(), await platform()));
    const book = XLSX.read(await zip.file("p-test-project/datasets/ds-test-dicom/dataset_description.xlsx")!.async("uint8array"));
    const rows = XLSX.utils.sheet_to_json<string[]>(book.Sheets[book.SheetNames[0]], { header: 1 });
    expect(rows).toContainEqual(["Title", "test_dicom"]);
    expect(rows).toContainEqual(["Type", "measurements"]);
  });

  it("reads back as the same project, every folder already on the platform", async () => {
    const project = await example();
    const r = await readBack(await bundleZip(project, await platform()), await platform());
    expect(r.errors).toEqual([]);
    expect(r.project).toEqual(project);
    expect(r.warnings).toHaveLength(7);
    expect(r.warnings[0]).toMatch(/already on the platform/);
  });

  it("reads back an uploaded project's bundled items, with the same ports and steps", async () => {
    const catalogue = await platform();
    const { project, bundled } = demoBundle(catalogue);
    const r = await readBack(await bundleZip(project, withBundled(catalogue, bundled)), catalogue);
    expect(r.errors).toEqual([]);
    const shape = (c: Catalogue) => ({
      datasets: c.datasets.map(d => [d.id, d.name, d.category]),
      workflows: c.workflows.map(w => [w.id, w.name, w.type, w.inputs, w.outputs, w.steps]),
      tools: c.tools.map(t => [t.id, t.name, t.type]),
    });
    expect(shape(r.bundled)).toEqual(shape(bundled));
  });
});

describe("demoBundle", () => {
  it("is the Test Project with one bundled dataset, workflow and tool", async () => {
    const catalogue = await platform();
    const { project, bundled } = demoBundle(catalogue);
    expect(project.project).toEqual({ id: "p-test-project-demo", title: "Test Project (bundled demo)" });
    const assays = project.investigations[0].studies[0].assays;
    expect(assays[0].inputs[0].source).toEqual({ kind: "existing", datasetId: "ds-demo-mri" });
    expect(assays[1].workflowId).toBe("wf-demo-image-conversion");
    expect([bundled.datasets.length, bundled.workflows.length, bundled.tools.length]).toEqual([1, 1, 1]);
  });

  it("writes only its bundled items, and passes every check", async () => {
    const catalogue = await platform();
    const { project, bundled } = demoBundle(catalogue);
    const blob = await bundleZip(project, withBundled(catalogue, bundled), { only: "bundled" });
    expect((await paths(blob)).filter(p => p.endsWith("dataset_description.xlsx")).map(p => p.split("/")[2]))
      .toEqual(["ds-demo-mri", "wf-demo-image-conversion"]);
    const r = await readBack(blob, catalogue);
    expect([r.errors, r.warnings]).toEqual([[], []]);
    expect(r.project?.project.id).toBe("p-test-project-demo");
  });

  it("leaves the example it copies untouched", async () => {
    const catalogue = await platform();
    const before: IsaProject = await example();
    demoBundle(catalogue);
    expect(await example()).toEqual(before);
  });
});
