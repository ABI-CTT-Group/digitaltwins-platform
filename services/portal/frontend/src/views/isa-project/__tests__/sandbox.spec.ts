import { describe, expect, it } from "vitest";
import { fixtureSource } from "../adapter/isaProjectSource";
import { isSandboxId, parseSandboxId, resolveSandboxTrail, SANDBOX_ID, sandboxChildren, sandboxProgramme } from "../sandbox";
import type { IsaProjectEntry } from "../sandbox";

const entries = async (): Promise<IsaProjectEntry[]> => {
  const example = await fixtureSource.loadExample("example-test-project");
  return [
    { project: example, source: "example", exampleId: "example-test-project" },
    { project: { ...example, project: { id: "p-mine", title: "My study plan" } }, source: "upload" },
  ];
};

describe("sandbox programme", () => {
  it("is one programme with a plain-language description", () => {
    expect(sandboxProgramme()).toMatchObject({
      seekId: SANDBOX_ID, name: "ISA projects", category: "Programmes",
      description: expect.stringContaining("nothing here is saved to the platform"),
    });
  });

  it("tells sandbox ids from real SEEK ids", () => {
    expect(isSandboxId("isa-sandbox")).toBe(true);
    expect(isSandboxId("isa-sandbox:p-test-project:i-test")).toBe(true);
    expect(isSandboxId("12")).toBe(false);
  });

  it("lists each ISA project as a project, then its investigations, studies and assays", async () => {
    const e = await entries();
    const projects = sandboxChildren(SANDBOX_ID, "Programmes", e);
    expect(projects.map(p => [p.seekId, p.name, p.category])).toEqual([
      ["isa-sandbox:p-test-project", "Test Project (example)", "Projects"],
      ["isa-sandbox:p-mine", "My study plan", "Projects"],
    ]);
    expect(projects[0].description).toContain("Example ISA project");
    expect(projects[1].description).toContain("Uploaded ISA project");

    const invs = sandboxChildren("isa-sandbox:p-test-project", "Projects", e);
    expect(invs.map(i => [i.seekId, i.category])).toEqual([["isa-sandbox:p-test-project:i-test", "Investigations"]]);

    const studies = sandboxChildren("isa-sandbox:p-test-project:i-test", "Investigations", e);
    expect(studies.map(s => [s.seekId, s.name, s.category])).toEqual([
      ["isa-sandbox:p-test-project:i-test:s-test", "Test Study", "Studies"],
    ]);
    expect(studies[0].description).toBe("4 assays");

    const assays = sandboxChildren("isa-sandbox:p-test-project:i-test:s-test", "Studies", e);
    expect(assays.map(a => [a.seekId, a.category, a.tag])[0])
      .toEqual(["isa-sandbox:p-test-project:i-test:s-test:a-cohort", "Assays", "notebook"]);
  });

  it("returns nothing for an id that matches no project", async () => {
    expect(sandboxChildren("isa-sandbox:nope", "Projects", await entries())).toEqual([]);
  });

  it("parses an id back into its parts", () => {
    expect(parseSandboxId("isa-sandbox:p-test-project:i-test:s-test"))
      .toEqual({ projectId: "p-test-project", investigationId: "i-test", studyId: "s-test" });
    expect(parseSandboxId("isa-sandbox")).toEqual({});
    expect(parseSandboxId("12")).toBeNull();
  });
});

describe("resolveSandboxTrail", () => {
  it("starts at the one ISA projects programme", async () => {
    expect(resolveSandboxTrail([], await entries())).toEqual({
      items: [sandboxProgramme()], breadcrumbs: [], currentCategory: "Programmes",
    });
  });

  it("walks a trail down to a study's assays, with named crumbs", async () => {
    const r = resolveSandboxTrail(
      ["isa-sandbox", "isa-sandbox:p-test-project", "isa-sandbox:p-test-project:i-test", "isa-sandbox:p-test-project:i-test:s-test"],
      await entries(),
    );
    expect(r.breadcrumbs.map(b => [b.name, b.category]))
      .toEqual([["ISA projects", "Programmes"], ["Test Project (example)", "Projects"], ["Test Investigation", "Investigations"], ["Test Study", "Studies"]]);
    expect(r.currentCategory).toBe("Assays");
    expect(r.items).toHaveLength(4);
  });

  it("stops at an id it can't find, so the caller can shorten the URL", async () => {
    const r = resolveSandboxTrail(["isa-sandbox", "isa-sandbox:gone", "isa-sandbox:gone:i"], await entries());
    expect(r.breadcrumbs.map(b => b.seekId)).toEqual(["isa-sandbox"]);
    expect(r.currentCategory).toBe("Projects");
    expect(r.items.map(i => i.name)).toEqual(["Test Project (example)", "My study plan"]);
  });
});
