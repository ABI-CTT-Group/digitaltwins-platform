// Where the ISA project prototype gets its data. Only the fixture source exists: it reads bundled
// JSON and never calls a server. A real source would implement the same interface over the API.
import type { Catalogue, IsaProject } from "../model/types";
import catalogueJson from "../fixtures/catalogue.json";
import breastPilotJson from "../fixtures/example-breast-pilot.json";

export interface IsaProjectSource {
  listExamples(): Promise<{ id: string; title: string }[]>;
  loadExample(id: string): Promise<IsaProject>;
  catalogue(): Promise<Catalogue>;
}

const copy = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

const examples: Record<string, unknown> = { "example-breast-pilot": breastPilotJson };
/** Bump when a shipped example changes, so browsers that stored an older one get the new one. */
export const EXAMPLE_RELEASE = 5;

export const fixtureSource: IsaProjectSource = {
  async listExamples() {
    return Object.entries(examples).map(([id, json]) => ({ id, title: (json as IsaProject).project.title }));
  },
  async loadExample(id) {
    if (!(id in examples)) throw new Error(`No example ${id}`);
    return copy<IsaProject>(examples[id]);
  },
  async catalogue() {
    return copy<Catalogue>(catalogueJson);
  },
};
