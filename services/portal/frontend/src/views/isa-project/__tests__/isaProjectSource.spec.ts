import { describe, expect, it } from "vitest";
import { fixtureSource, IsaProjectUploadError } from "../adapter/isaProjectSource";
import { validateIsaProject } from "../model/isaProject";

describe("fixtureSource", () => {
  it("ships the Te Whatu Ora breast pilot example, with no \"test\" anywhere the pilot study shows", async () => {
    expect(await fixtureSource.listExamples()).toEqual([{ id: "example-breast-pilot", title: "Breast" }]);
    const example = await fixtureSource.loadExample("example-breast-pilot");
    expect(example.project.id).toBe("p-breast");
    const inv = example.investigations[0];
    expect([inv.id, inv.title]).toEqual(["i-breast-radiology-report", "Breast Radiology Report"]);
    expect(inv.studies.map(s => [s.id, s.title])).toEqual([
      ["s-breast-pilot", "Te Whatu Ora Breast Pilot"],
      ["s-image-pipeline-test", "Image pipeline test"],
    ]);
    expect(JSON.stringify(inv.studies[0])).not.toMatch(/test/i);
    const { datasets } = await fixtureSource.catalogue();
    expect(JSON.stringify(datasets)).not.toMatch(/test/i);
  });

  it("ships one example, mirroring the platform's Test Project", async () => {
    expect(await fixtureSource.listExamples()).toEqual([{ id: "example-breast-pilot", title: "Breast" }]);
  });

  const planned = (study: { assays: { id: string; inputs: { port: string; source: unknown }[] }[] }) =>
    study.assays.flatMap(a => a.inputs.flatMap(i => {
      const s = i.source as { kind: string; assayId: string; port: string } | null;
      return s?.kind === "planned" ? [`${s.assayId}/${s.port} -> ${a.id}/${i.port}`] : [];
    }));

  it("lays the pilot study out as the nine-assay breast pipeline, plus a standalone image visualisation", async () => {
    const study = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies[0];
    expect(study.assays.map(a => [a.id, a.title, a.type, a.workflowId])).toEqual([
      ["a-cohort", "1. Cohort selection", "notebook", "wf-mri-curation"],
      ["a-convert", "2. Image conversion", "script", "wf-image-conversion"],
      ["a-initial-inference", "3. Initial inference", "script", "wf-mock-inference"],
      ["a-breast-app", "4. Image annotation", "gui", "wf-lesion-curator"],
      ["a-finetune", "5. Model fine-tuning", "notebook", "wf-mock-model-finetuning"],
      ["a-inference", "6. Inference", "script", "wf-mock-inference"],
      ["a-breast-model", "7. Generate breast model", "script", "wf-mock-breast-model"],
      ["a-lesion-report", "8. Lesion position reporting", "gui", "wf-lesion-curator"],
      ["a-statistics", "9. Statistical analysis", "notebook", "wf-mock-statistical-analysis"],
      ["a-visualise", "Image visualisation", "gui", "wf-volview"],
    ]);
    expect(planned(study)).toEqual([
      "a-cohort/curated_dataset -> a-convert/dicom_input",
      "a-convert/nifti_output -> a-initial-inference/mri_nifti",
      "a-convert/nrrd_output -> a-breast-app/contrast_pre_nrrd",
      "a-initial-inference/lesion_inference_nifti -> a-breast-app/model_predicted_LPS_nii",
      "a-breast-app/clinician_validated_nii_LPS -> a-finetune/clinician_validated_masks",
      "a-convert/nifti_output -> a-inference/mri_nifti",
      "a-finetune/finetuned_models -> a-inference/skin_model",
      "a-finetune/finetuned_models -> a-inference/outer_rib_model",
      "a-finetune/finetuned_models -> a-inference/sternum_model",
      "a-finetune/finetuned_models -> a-inference/lesion_model",
      "a-inference/skin_inference_nifti -> a-breast-model/skin_inference_nifti",
      "a-inference/outer_rib_inference_nifti -> a-breast-model/outer_rib_inference_nifti",
      "a-inference/sternum_inference_nifti -> a-breast-model/sternum_inference_nifti",
      "a-convert/nrrd_output -> a-lesion-report/contrast_pre_nrrd",
      "a-inference/lesion_inference_nifti -> a-lesion-report/model_predicted_LPS_nii",
      "a-breast-model/breast_mesh -> a-lesion-report/breast_surface_glb",
      "a-lesion-report/mask_meta_json -> a-statistics/lesion_position_reports",
    ]);
    const visualise = study.assays.find(a => a.id === "a-visualise")!;
    expect(visualise.inputs).toEqual([{ port: "dicom_file", source: { kind: "existing", datasetId: "ds-converted" } }]);
    expect(study.assays.some(a => a.inputs.some(i => i.source?.kind === "planned" && i.source.assayId === "a-visualise")))
      .toBe(false);
  });

  it("titles the example's assays without the word assay, for an audience that may not know it", async () => {
    const studies = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies;
    expect(studies.flatMap(s => s.assays.map(a => a.title)).filter(t => /\bassay\b/i.test(t))).toEqual([]);
  });

  it("keeps the original four assays and their flow in the Image pipeline test study", async () => {
    const study = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies[1];
    expect(study.assays.map(a => [a.id, a.title, a.workflowId, a.cohort])).toEqual([
      ["a-pipeline-cohort", "1. Cohort selection", "wf-mri-curation", []],
      ["a-pipeline-convert", "2. Image conversion", "wf-image-conversion", [1]],
      ["a-pipeline-visualise", "3. Image visualisation", "wf-volview", [1]],
      ["a-pipeline-breast-app", "4. Breast app", "wf-lesion-curator", [1]],
    ]);
    expect(planned(study)).toEqual([
      "a-pipeline-cohort/curated_dataset -> a-pipeline-convert/dicom_input",
      "a-pipeline-convert/nifti_output -> a-pipeline-visualise/dicom_file",
      "a-pipeline-convert/nrrd_output -> a-pipeline-breast-app/contrast_pre_nrrd",
    ]);
  });

  it("lets several outputs of one assay promise the same dataset, as the platform does", async () => {
    const study = (await fixtureSource.loadExample("example-breast-pilot")).investigations[0].studies[0];
    const names = (id: string) => [...new Set(study.assays.find(a => a.id === id)!.outputs.map(o => o.datasetName))];
    expect(names("a-convert")).toEqual(["converted"]);
    expect(names("a-initial-inference")).toEqual(["initial_inference"]);
    expect(names("a-breast-app")).toEqual(["breast_app_output"]);
    expect(names("a-lesion-report")).toEqual(["lesion_position_report"]);
    expect(study.assays.find(a => a.id === "a-breast-app")!.outputs).toHaveLength(12);
  });

  it("catalogues the platform's workflows (real and stand-in), tools and datasets", async () => {
    const { workflows, tools, datasets } = await fixtureSource.catalogue();
    expect(workflows.map(w => w.name)).toEqual([
      "workflow_mri_curation", "workflow_image_conversion", "workflow_volview", "workflow_Lesion-Ground-Truth-Curator",
      "workflow_breast_inference", "workflow_model_finetuning", "workflow_breast_model",
      "workflow_statistical_analysis",
    ]);
    expect(tools.map(t => t.name)).toEqual([
      "tool_mri_curation", "tool_dicom_to_nifti", "tool_dicom_to_nrrd", "tool_volview", "tool_Lesion-Ground-Truth-Curator",
      "tool_download_samples", "tool_skin_inference", "tool_outer_rib_inference",
      "tool_sternum_inference", "tool_lesion_inference", "tool_model_finetuning",
      "tool_point_cloud_generation", "tool_mesh_fitting", "tool_statistical_analysis",
    ]);
    expect(datasets.map(d => d.name)).toEqual([
      "dicom", "curated_dataset", "converted", "data_breast_app", "model_breast_app", "pretrained_models",
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
