import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssayGuiContext, AssayGuiFile } from "@/models/types";

import { buildVolViewQuery } from "../volviewParams";

const file = (name: string, encoded = name): AssayGuiFile => ({
  name, subjectId: "sub-1", sampleId: "sam-1",
  url: `/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/${encoded}`,
});

const context = (...files: AssayGuiFile[]): AssayGuiContext => ({
  assayId: "43",
  tool: { name: "tool_volview", path: "/tool-builds/x/primary/my-app.umd.js", expose: "x" },
  inputs: [{ name: "dicom_file", datasetUuid: "ds-1", sampleType: "dicom", files }],
});

// vtk.js percent-decodes each query value once before VolView reads it, so parse the way it does.
const params = (query: string) => new URLSearchParams(query);

afterEach(() => vi.restoreAllMocks());

describe("buildVolViewQuery", () => {
  it("lists the input files as VolView's bracketed urls and names, keeping the assay id", () => {
    const q = params(buildVolViewQuery(context(file("a b.dcm", "a%20b.dcm"), file("c.dcm"))));

    expect(q.get("assay")).toBe("43");
    expect(q.get("urls")).toBe(
      "[/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a%20b.dcm," +
      "/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/c.dcm]",
    );
    expect(q.get("names")).toBe("[a b.dcm,c.dcm]");
    expect(q.has("token")).toBe(false); // VolView ignores it for urls=; the token travels in a cookie instead
  });

  it("concatenates the files of every input in order", () => {
    const ctx = context(file("a.dcm"));
    ctx.inputs.push({ name: "mask", datasetUuid: "ds-2", sampleType: "nifti", files: [file("m.nii")] });

    expect(params(buildVolViewQuery(ctx)).get("names")).toBe("[a.dcm,m.nii]");
  });

  it("skips a file whose name would split VolView's comma list, and says so", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const q = params(buildVolViewQuery(context(file("x,y.dcm", "x%2Cy.dcm"), file("ok.dcm"))));

    expect(q.get("names")).toBe("[ok.dcm]");
    expect(q.get("urls")).not.toContain("x%2Cy");
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0].join(" ")).toContain("x,y.dcm");
  });
});
