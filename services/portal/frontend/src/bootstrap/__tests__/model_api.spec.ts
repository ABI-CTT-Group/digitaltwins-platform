import { beforeEach, describe, expect, it, vi } from "vitest";

const dtApi = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi }));

import { useModelFhirDraft, useModels, useUpsertModelAnnotation } from "@/bootstrap/model_api";

beforeEach(() => vi.resetAllMocks());

describe("useModels", () => {
  it("lists open model sessions and registered models, newest first", async () => {
    dtApi.get.mockImplementation(async (path: string) =>
      path === "/datasets/uploads"
        ? { uploads: [{ uploadId: "u1", name: "Staged", status: "staged", fhirMode: "none",
                        createdAt: "2026-10-12T10:00:00", updatedAt: "" }] }
        : { models: [{ datasetUuid: "d1", datasetName: "Skin", fhirStatus: "completed",
                       createdAt: "2026-10-11T10:00:00" }] });

    const models = await useModels();

    expect(dtApi.get).toHaveBeenCalledWith("/datasets/uploads", { category: "models" });
    expect(dtApi.get).toHaveBeenCalledWith("/models");
    expect(models.map((m) => [m.id, m.status])).toEqual([["upload:u1", "pending"], ["dataset:d1", "completed"]]);
    expect(models[1]).toMatchObject({ uuid: "d1", name: "Skin", hasAnnotation: true });
  });
});

describe("useModelFhirDraft", () => {
  it("reads the model descriptions of a staged upload", async () => {
    dtApi.get.mockResolvedValue({ descriptions: { model: { uuid: "", name: "Skin", description: "d", version: "" } } });

    expect(await useModelFhirDraft("upload:u1")).toEqual({ description: "d", version: "" });
    expect(dtApi.get).toHaveBeenCalledWith("/datasets/uploads/u1/fhir/tree");
  });
});

describe("useUpsertModelAnnotation", () => {
  it("stores the draft of a staged upload", async () => {
    await useUpsertModelAnnotation("upload:u1", { description: "nnUNet", version: "2.1" });

    expect(dtApi.put).toHaveBeenCalledWith("/datasets/uploads/u1/fhir/annotation",
      { descriptions: { model: { description: "nnUNet", version: "2.1" } } });
  });

  it("stores the annotation of a registered model", async () => {
    await useUpsertModelAnnotation("dataset:d1", { description: "", version: "1" });

    expect(dtApi.put).toHaveBeenCalledWith("/datasets/d1/fhir/annotation",
      { descriptions: { model: { description: "", version: "1" } } });
  });
});
