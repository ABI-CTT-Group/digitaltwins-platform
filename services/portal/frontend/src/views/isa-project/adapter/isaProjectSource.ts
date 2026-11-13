// Where the ISA project prototype gets its data. Only the fixture source exists: it reads bundled
// JSON and never calls a server. A real source would implement the same interface over the API.
import type { Catalogue, IsaProject } from "../model/types";
import { validateIsaProject } from "../model/isaProject";
import catalogueJson from "../fixtures/catalogue.json";
import testProjectJson from "../fixtures/example-test-project.json";

export interface IsaProjectSource {
  listExamples(): Promise<{ id: string; title: string }[]>;
  loadExample(id: string): Promise<IsaProject>;
  /** Parse and validate an uploaded draft-schema JSON; rejects with IsaProjectUploadError. */
  parseUpload(text: string): Promise<IsaProject>;
  catalogue(): Promise<Catalogue>;
}

export class IsaProjectUploadError extends Error {
  constructor(public errors: string[]) {
    super(errors.join("\n"));
    this.name = "IsaProjectUploadError";
  }
}

const copy = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

const examples: Record<string, unknown> = { "example-test-project": testProjectJson };

export const fixtureSource: IsaProjectSource = {
  async listExamples() {
    return Object.entries(examples).map(([id, json]) => ({ id, title: (json as IsaProject).project.title }));
  },
  async loadExample(id) {
    if (!(id in examples)) throw new Error(`No example ${id}`);
    return copy<IsaProject>(examples[id]);
  },
  async parseUpload(text) {
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      throw new IsaProjectUploadError(["The file is not valid JSON."]);
    }
    const result = validateIsaProject(json, copy<Catalogue>(catalogueJson));
    if (!result.ok) throw new IsaProjectUploadError(result.errors);
    return result.project;
  },
  async catalogue() {
    return copy<Catalogue>(catalogueJson);
  },
};
