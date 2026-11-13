import { describe, expect, it } from "vitest";
import { fixtureSource, IsaProjectUploadError } from "../adapter/isaProjectSource";
import { validateIsaProject } from "../model/isaProject";

describe("fixtureSource", () => {
  it("ships one example, mirroring the platform's Test Project", async () => {
    expect(await fixtureSource.listExamples()).toEqual([{ id: "example-test-project", title: "Test Project (example)" }]);
  });

  it("wires the example as the Test Project runs: 1 -> 2 -> 3, and 2 -> 4", async () => {
    const study = (await fixtureSource.loadExample("example-test-project")).investigations[0].studies[0];
    expect(study.assays.map(a => [a.id, a.title, a.workflowId, a.cohort])).toEqual([
      ["a-cohort", "Test Assay 1: cohort selection", "wf-mri-curation", []],
      ["a-convert", "Test Assay 2: image conversion", "wf-image-conversion", [1]],
      ["a-visualise", "Test Assay 3: image visualisation", "wf-volview", [1]],
      ["a-breast-app", "Test Assay 4: breast app", "wf-lesion-curator", [1]],
    ]);
    const planned = study.assays.flatMap(a => a.inputs.flatMap(i =>
      i.source?.kind === "planned" ? [`${i.source.assayId}/${i.source.port} -> ${a.id}/${i.port}`] : []));
    expect(planned).toEqual([
      "a-cohort/curated_dataset -> a-convert/dicom_input",
      "a-convert/nifti_output -> a-visualise/dicom_file",
      "a-convert/nrrd_output -> a-breast-app/contrast_pre_nrrd",
    ]);
  });

  it("lets several outputs of one assay promise the same dataset, as the platform does", async () => {
    const study = (await fixtureSource.loadExample("example-test-project")).investigations[0].studies[0];
    const names = (id: string) => [...new Set(study.assays.find(a => a.id === id)!.outputs.map(o => o.datasetName))];
    expect(names("a-convert")).toEqual(["test_converted"]);
    expect(names("a-breast-app")).toEqual(["test_breast_app_output"]);
    expect(study.assays.find(a => a.id === "a-breast-app")!.outputs).toHaveLength(12);
  });

  it("catalogues the platform's real workflows, tools and test datasets", async () => {
    const { workflows, tools, datasets } = await fixtureSource.catalogue();
    expect(workflows.map(w => w.name)).toEqual([
      "workflow_mri_curation", "workflow_image_conversion", "workflow_volview", "workflow_Lesion-Ground-Truth-Curator",
    ]);
    expect(tools.map(t => t.name)).toEqual([
      "tool_mri_curation", "tool_dicom_to_nifti", "tool_dicom_to_nrrd", "tool_volview", "tool_Lesion-Ground-Truth-Curator",
    ]);
    expect(datasets.map(d => d.name)).toEqual([
      "test_dicom", "test_curated_dataset", "test_converted", "test_data_breast_app", "test_model_breast_app",
    ]);
  });

  it("ships examples that are valid against its own catalogue", async () => {
    const catalogue = await fixtureSource.catalogue();
    const examples = await fixtureSource.listExamples();
    expect(examples.length).toBeGreaterThan(0);
    for (const { id } of examples) {
      const r = validateIsaProject(await fixtureSource.loadExample(id), catalogue);
      expect(r.ok ? [] : r.errors).toEqual([]);
    }
  });

  it("names a real tool for every workflow step in the catalogue", async () => {
    const { workflows, tools } = await fixtureSource.catalogue();
    const toolIds = new Set(tools.map(t => t.id));
    expect(workflows.flatMap(w => w.steps).filter(s => !toolIds.has(s.toolId))).toEqual([]);
  });

  it("never names a step like a workflow input or output (the CWL graph keys nodes by name)", async () => {
    const { workflows } = await fixtureSource.catalogue();
    const clashes = workflows.flatMap(w => {
      const ports = new Set([...w.inputs, ...w.outputs].map(p => p.name));
      return w.steps.filter(s => ports.has(s.id)).map(s => `${w.id}/${s.id}`);
    });
    expect(clashes).toEqual([]);
  });

  it("hands out a fresh copy of an example each time", async () => {
    const [{ id }] = await fixtureSource.listExamples();
    const first = await fixtureSource.loadExample(id);
    first.project.title = "changed";
    expect((await fixtureSource.loadExample(id)).project.title).not.toBe("changed");
  });

  it("parses a valid upload", async () => {
    const [{ id }] = await fixtureSource.listExamples();
    const text = JSON.stringify(await fixtureSource.loadExample(id));
    expect(await fixtureSource.parseUpload(text)).toEqual(JSON.parse(text));
  });

  it("rejects an upload that isn't JSON", async () => {
    await expect(fixtureSource.parseUpload("{oops")).rejects.toEqual(
      new IsaProjectUploadError(["The file is not valid JSON."]));
  });

  it("rejects an upload that doesn't match the draft schema, listing why", async () => {
    const err = await fixtureSource.parseUpload('{"schemaVersion":"0.1-draft"}').catch(e => e);
    expect(err).toBeInstanceOf(IsaProjectUploadError);
    expect(err.errors).toContain("project needs an id and a title");
  });
});
