import { describe, expect, it } from "vitest";
import { fixtureSource, IsaProjectUploadError } from "../adapter/isaProjectSource";
import { validateIsaProject } from "../model/isaProject";

describe("fixtureSource", () => {
  it("ships one example, the breast pilot", async () => {
    expect(await fixtureSource.listExamples()).toEqual([{ id: "example-breast-pilot", title: "Breast pilot (example)" }]);
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
