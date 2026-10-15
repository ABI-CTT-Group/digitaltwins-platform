import { describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/keycloak", () => ({ isAuthenticated: () => false }));
vi.mock("@/store/auth_store", () => ({ useAuthStore: () => ({ updateAuthState: () => {} }) }));

import router from "../index";

describe("catalogue routes", () => {
  it.each([
    ["CatalogueDashboardView", "/catalogue"],
    ["UploadMeasurementsDataset", "/catalogue/measurements"],
    ["UploadModelDataset", "/catalogue/models"],
    ["UploadToolDataset", "/catalogue/tools"],
    ["UploadWorkflowDataset", "/catalogue/workflows"],
    ["ToolsViewer", "/catalogue/workflow-assembler"],
  ])("serves %s at %s", (name, path) => {
    expect(router.resolve({ name }).path).toBe(path);
  });

  it("keeps a measurement's FHIR preview under its catalogue page", () => {
    expect(router.resolve({ name: "MeasurementFhirPreview", params: { id: "m1" } }).path)
      .toBe("/catalogue/measurements/m1/preview");
  });

  it("sends the bare /upload-dataset parent to the catalogue", async () => {
    await router.push("/upload-dataset");
    expect(router.currentRoute.value.path).toBe("/catalogue");
  });
});
