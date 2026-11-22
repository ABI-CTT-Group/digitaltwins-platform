import { describe, expect, it } from "vitest";
import { fixtureSource } from "../adapter/isaProjectSource";
import { isSandboxId, knownProgrammes, parseSandboxId, programmeNamed, resolveSandboxTrail, SANDBOX_ID, sandboxChildren, sandboxProgrammes } from "../sandbox";
import type { IsaProjectEntry } from "../sandbox";

const entries = async (): Promise<IsaProjectEntry[]> => {
  const example = await fixtureSource.loadExample("example-breast-pilot");
  return [
    { project: example, source: "example", exampleId: "example-breast-pilot" },
    { project: { ...example, project: { id: "p-mine", title: "My study plan" } }, source: "upload" },
  ];
};

const RESEARCH = { id: "isa-radiology-research", name: "Radiology research" };
/** The two entries, plus an upload filed in a programme of its own. */
const withResearch = async (): Promise<IsaProjectEntry[]> => {
  const e = await entries();
  return [...e, { project: { ...e[0].project, project: { id: "p-research", title: "Research plan" } }, source: "upload", programme: RESEARCH }];
};

describe("sandbox programme", () => {
  it("is the built-in programme, described by how many projects it holds", async () => {
    expect(sandboxProgrammes(await entries())).toEqual([{
      seekId: "te-whatu-ora-radiology-reporting", name: "Te Whatu Ora Radiology Reporting", category: "Programmes",
      description: "2 projects",
    }]);
    expect(sandboxProgrammes((await entries()).slice(0, 1))[0].description).toBe("1 project");
  });

  it("lists each programme a project was filed in after the built-in one", async () => {
    expect(sandboxProgrammes(await withResearch()).map(p => [p.seekId, p.name, p.description])).toEqual([
      ["te-whatu-ora-radiology-reporting", "Te Whatu Ora Radiology Reporting", "2 projects"],
      ["isa-radiology-research", "Radiology research", "1 project"],
    ]);
    expect(knownProgrammes(await withResearch())).toEqual([
      { id: "te-whatu-ora-radiology-reporting", name: "Te Whatu Ora Radiology Reporting" }, RESEARCH,
    ]);
  });

  it("keeps the built-in programme even with no projects in it", () => {
    expect(sandboxProgrammes([]).map(p => [p.seekId, p.description])).toEqual([["te-whatu-ora-radiology-reporting", "0 projects"]]);
  });

  it("turns a typed name into a programme, matching one already known by its name", async () => {
    const e = await withResearch();
    expect(programmeNamed("  Cardiac  imaging ", e)).toEqual({ id: "isa-cardiac-imaging", name: "Cardiac imaging" });
    expect(programmeNamed("radiology RESEARCH", e)).toEqual(RESEARCH);
    expect(programmeNamed("Te Whatu Ora radiology reporting", e)).toEqual({ id: SANDBOX_ID, name: "Te Whatu Ora Radiology Reporting" });
    expect(programmeNamed("Ōtautahi", e)).toEqual({ id: "isa-otautahi", name: "Ōtautahi" });
    expect(programmeNamed("???", e)).toEqual({ id: "isa-programme", name: "???" });
  });

  it("lists only a programme's own projects", async () => {
    const e = await withResearch();
    expect(sandboxChildren(SANDBOX_ID, "Programmes", e).map(p => p.name)).toEqual(["Breast", "My study plan"]);
    expect(sandboxChildren("isa-radiology-research", "Programmes", e).map(p => [p.seekId, p.name]))
      .toEqual([["isa-radiology-research:p-research", "Research plan"]]);
  });

  it("tells sandbox ids from real SEEK ids", () => {
    expect(isSandboxId("te-whatu-ora-radiology-reporting")).toBe(true);
    expect(isSandboxId("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report")).toBe(true);
    expect(isSandboxId("isa-radiology-research:p-research")).toBe(true);
    expect(isSandboxId("12")).toBe(false);
  });

  it("lists each ISA project as a project, then its investigations, studies and assays", async () => {
    const e = await entries();
    const projects = sandboxChildren(SANDBOX_ID, "Programmes", e);
    expect(projects.map(p => [p.seekId, p.name, p.category])).toEqual([
      ["te-whatu-ora-radiology-reporting:p-breast", "Breast", "Projects"],
      ["te-whatu-ora-radiology-reporting:p-mine", "My study plan", "Projects"],
    ]);
    expect(projects.map(p => p.description)).toEqual(["1 investigation", "1 investigation"]);

    const invs = sandboxChildren("te-whatu-ora-radiology-reporting:p-breast", "Projects", e);
    expect(invs.map(i => [i.seekId, i.category, i.description])).toEqual([["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "Investigations", "2 studies"]]);

    const studies = sandboxChildren("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "Investigations", e);
    expect(studies.map(s => [s.seekId, s.name, s.category])).toEqual([
      ["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot", "Te Whatu Ora Breast Pilot", "Studies"],
      ["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-image-pipeline-test", "Image pipeline test", "Studies"],
    ]);
    expect(studies.map(s => s.description)).toEqual(["10 assays", "4 assays"]);

    const assays = sandboxChildren("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot", "Studies", e);
    expect(assays.map(a => [a.seekId, a.category, a.tag])[0])
      .toEqual(["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot:a-cohort", "Assays", "notebook"]);
  });

  it("returns nothing for an id that matches no project", async () => {
    expect(sandboxChildren("te-whatu-ora-radiology-reporting:nope", "Projects", await entries())).toEqual([]);
  });

  it("parses an id back into its parts", () => {
    expect(parseSandboxId("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot"))
      .toEqual({ programmeId: SANDBOX_ID, projectId: "p-breast", investigationId: "i-breast-radiology-report", studyId: "s-breast-pilot" });
    expect(parseSandboxId("te-whatu-ora-radiology-reporting")).toEqual({ programmeId: SANDBOX_ID });
    expect(parseSandboxId("isa-radiology-research:p-research")).toEqual({ programmeId: "isa-radiology-research", projectId: "p-research" });
    expect(parseSandboxId("12")).toBeNull();
  });
});

describe("resolveSandboxTrail", () => {
  it("starts at the programmes", async () => {
    const e = await withResearch();
    expect(resolveSandboxTrail([], e)).toEqual({
      items: sandboxProgrammes(e), breadcrumbs: [], currentCategory: "Programmes",
    });
  });

  it("walks a trail through a named programme", async () => {
    const r = resolveSandboxTrail(["isa-radiology-research", "isa-radiology-research:p-research"], await withResearch());
    expect(r.breadcrumbs.map(b => b.name)).toEqual(["Radiology research", "Research plan"]);
    expect(r.items.map(i => i.seekId)).toEqual(["isa-radiology-research:p-research:i-breast-radiology-report"]);
  });

  it("doesn't find a project under a programme it isn't in", async () => {
    const r = resolveSandboxTrail([SANDBOX_ID, `${SANDBOX_ID}:p-research`], await withResearch());
    expect(r.breadcrumbs).toHaveLength(1);
  });

  it("walks a trail down to a study's assays, with named crumbs", async () => {
    const r = resolveSandboxTrail(
      ["te-whatu-ora-radiology-reporting", "te-whatu-ora-radiology-reporting:p-breast", "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot"],
      await entries(),
    );
    expect(r.breadcrumbs.map(b => [b.name, b.category]))
      .toEqual([["Te Whatu Ora Radiology Reporting", "Programmes"], ["Breast", "Projects"], ["Breast Radiology Report", "Investigations"], ["Te Whatu Ora Breast Pilot", "Studies"]]);
    expect(r.currentCategory).toBe("Assays");
    expect(r.items).toHaveLength(10);
  });

  it("stops at an id it can't find, so the caller can shorten the URL", async () => {
    const r = resolveSandboxTrail(["te-whatu-ora-radiology-reporting", "te-whatu-ora-radiology-reporting:gone", "te-whatu-ora-radiology-reporting:gone:i"], await entries());
    expect(r.breadcrumbs.map(b => b.seekId)).toEqual(["te-whatu-ora-radiology-reporting"]);
    expect(r.currentCategory).toBe("Projects");
    expect(r.items.map(i => i.name)).toEqual(["Breast", "My study plan"]);
  });
});
