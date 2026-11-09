import { describe, expect, it } from "vitest";
import { fixtureSource } from "../adapter/isaProjectSource";
import { isSandboxId, parseSandboxId, SANDBOX_ID, sandboxChildren, sandboxProgramme } from "../sandbox";
import type { IsaProjectEntry } from "../sandbox";

const entries = async (): Promise<IsaProjectEntry[]> => {
  const example = await fixtureSource.loadExample("example-breast-pilot");
  return [
    { project: example, source: "example", exampleId: "example-breast-pilot" },
    { project: { ...example, project: { id: "p-mine", title: "My study plan" } }, source: "upload" },
  ];
};

describe("sandbox programme", () => {
  it("is one programme with a plain-language description", () => {
    expect(sandboxProgramme()).toMatchObject({
      seekId: SANDBOX_ID, name: "Study design sandbox", category: "Programmes",
      description: expect.stringContaining("nothing here is saved to the platform"),
    });
  });

  it("tells sandbox ids from real SEEK ids", () => {
    expect(isSandboxId("isa-sandbox")).toBe(true);
    expect(isSandboxId("isa-sandbox:p-breast-pilot:i-breast")).toBe(true);
    expect(isSandboxId("12")).toBe(false);
  });

  it("lists each ISA project as a project, then its investigations, studies and assays", async () => {
    const e = await entries();
    const projects = sandboxChildren(SANDBOX_ID, "Programmes", e);
    expect(projects.map(p => [p.seekId, p.name, p.category])).toEqual([
      ["isa-sandbox:p-breast-pilot", "Breast pilot (example)", "Projects"],
      ["isa-sandbox:p-mine", "My study plan", "Projects"],
    ]);
    expect(projects[0].description).toContain("Example ISA project");
    expect(projects[1].description).toContain("Uploaded ISA project");

    const invs = sandboxChildren("isa-sandbox:p-breast-pilot", "Projects", e);
    expect(invs.map(i => [i.seekId, i.category])).toEqual([["isa-sandbox:p-breast-pilot:i-breast", "Investigations"]]);

    const studies = sandboxChildren("isa-sandbox:p-breast-pilot:i-breast", "Investigations", e);
    expect(studies.map(s => [s.seekId, s.name, s.category])).toEqual([
      ["isa-sandbox:p-breast-pilot:i-breast:s-pilot", "Breast pilot", "Studies"],
    ]);
    expect(studies[0].description).toBe("6 assays");

    const assays = sandboxChildren("isa-sandbox:p-breast-pilot:i-breast:s-pilot", "Studies", e);
    expect(assays.map(a => [a.seekId, a.category, a.tag])[0])
      .toEqual(["isa-sandbox:p-breast-pilot:i-breast:s-pilot:a-cohort", "Assays", "notebook"]);
  });

  it("returns nothing for an id that matches no project", async () => {
    expect(sandboxChildren("isa-sandbox:nope", "Projects", await entries())).toEqual([]);
  });

  it("parses an id back into its parts", () => {
    expect(parseSandboxId("isa-sandbox:p-breast-pilot:i-breast:s-pilot"))
      .toEqual({ projectId: "p-breast-pilot", investigationId: "i-breast", studyId: "s-pilot" });
    expect(parseSandboxId("isa-sandbox")).toEqual({});
    expect(parseSandboxId("12")).toBeNull();
  });
});
