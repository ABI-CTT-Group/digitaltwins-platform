import { describe, expect, it } from "vitest";
import { fixtureSource } from "../adapter/isaProjectSource";
import { isSandboxId, parseSandboxId, resolveSandboxTrail, SANDBOX_ID, sandboxChildren, sandboxProgramme } from "../sandbox";
import type { IsaProjectEntry } from "../sandbox";

const entries = async (): Promise<IsaProjectEntry[]> => {
  const example = await fixtureSource.loadExample("example-breast-pilot");
  return [
    { project: example, source: "example", exampleId: "example-breast-pilot" },
    { project: { ...example, project: { id: "p-mine", title: "My study plan" } }, source: "upload" },
  ];
};

describe("sandbox programme", () => {
  it("is one programme, described by how many projects it holds", async () => {
    expect(sandboxProgramme(await entries())).toEqual({
      seekId: "te-whatu-ora-radiology-reporting", name: "Te Whatu Ora Radiology Reporting", category: "Programmes",
      description: "2 projects",
    });
    expect(sandboxProgramme((await entries()).slice(0, 1)).description).toBe("1 project");
  });

  it("tells sandbox ids from real SEEK ids", () => {
    expect(isSandboxId("te-whatu-ora-radiology-reporting")).toBe(true);
    expect(isSandboxId("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report")).toBe(true);
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
    expect(invs.map(i => [i.seekId, i.category, i.description])).toEqual([["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "Investigations", "1 study"]]);

    const studies = sandboxChildren("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "Investigations", e);
    expect(studies.map(s => [s.seekId, s.name, s.category])).toEqual([
      ["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot", "Te Whatu Ora Breast Pilot", "Studies"],
    ]);
    expect(studies[0].description).toBe("4 assays");

    const assays = sandboxChildren("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot", "Studies", e);
    expect(assays.map(a => [a.seekId, a.category, a.tag])[0])
      .toEqual(["te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot:a-cohort", "Assays", "notebook"]);
  });

  it("returns nothing for an id that matches no project", async () => {
    expect(sandboxChildren("te-whatu-ora-radiology-reporting:nope", "Projects", await entries())).toEqual([]);
  });

  it("parses an id back into its parts", () => {
    expect(parseSandboxId("te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot"))
      .toEqual({ projectId: "p-breast", investigationId: "i-breast-radiology-report", studyId: "s-breast-pilot" });
    expect(parseSandboxId("te-whatu-ora-radiology-reporting")).toEqual({});
    expect(parseSandboxId("12")).toBeNull();
  });
});

describe("resolveSandboxTrail", () => {
  it("starts at the one Te Whatu Ora Radiology Reporting programme", async () => {
    const e = await entries();
    expect(resolveSandboxTrail([], e)).toEqual({
      items: [sandboxProgramme(e)], breadcrumbs: [], currentCategory: "Programmes",
    });
  });

  it("walks a trail down to a study's assays, with named crumbs", async () => {
    const r = resolveSandboxTrail(
      ["te-whatu-ora-radiology-reporting", "te-whatu-ora-radiology-reporting:p-breast", "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report", "te-whatu-ora-radiology-reporting:p-breast:i-breast-radiology-report:s-breast-pilot"],
      await entries(),
    );
    expect(r.breadcrumbs.map(b => [b.name, b.category]))
      .toEqual([["Te Whatu Ora Radiology Reporting", "Programmes"], ["Breast", "Projects"], ["Breast Radiology Report", "Investigations"], ["Te Whatu Ora Breast Pilot", "Studies"]]);
    expect(r.currentCategory).toBe("Assays");
    expect(r.items).toHaveLength(4);
  });

  it("stops at an id it can't find, so the caller can shorten the URL", async () => {
    const r = resolveSandboxTrail(["te-whatu-ora-radiology-reporting", "te-whatu-ora-radiology-reporting:gone", "te-whatu-ora-radiology-reporting:gone:i"], await entries());
    expect(r.breadcrumbs.map(b => b.seekId)).toEqual(["te-whatu-ora-radiology-reporting"]);
    expect(r.currentCategory).toBe("Projects");
    expect(r.items.map(i => i.name)).toEqual(["Breast", "My study plan"]);
  });
});
