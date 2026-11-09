// Draft "ISA project" format (prototype). It is a proposal to agree on, not a platform contract:
// nothing on the server reads it yet.

export const SCHEMA_VERSION = "0.1-draft";

export type AssayType = "script" | "notebook" | "gui";
export type Category = "measurements" | "models" | "tools" | "workflows";

/** Where an assay input's data comes from: a dataset already on the platform, or a planned
 *  dataset, i.e. an output another assay in the same study will produce when it runs. */
export type InputSource =
  | { kind: "existing"; datasetId: string }
  | { kind: "planned"; assayId: string; port: string };

export interface AssayInput { port: string; source: InputSource | null }
export interface AssayOutput { port: string; datasetName: string; category: Category }

export interface Assay {
  id: string;
  title: string;
  type: AssayType;
  workflowId: string | null;
  /** Subject indices to run; empty means every subject. */
  cohort: number[];
  inputs: AssayInput[];
  outputs: AssayOutput[];
}

export interface Study { id: string; title: string; assays: Assay[] }
export interface Investigation { id: string; title: string; studies: Study[] }

export interface IsaProject {
  schemaVersion: typeof SCHEMA_VERSION;
  project: { id: string; title: string };
  investigations: Investigation[];
}

// The platform side the prototype reads: what a real adapter would fetch from the API.
export interface Port { name: string; category: Category }
export interface WorkflowStep { id: string; toolId: string }
export interface CatalogueWorkflow {
  id: string;
  name: string;
  type: AssayType;
  inputs: Port[];
  outputs: Port[];
  steps: WorkflowStep[];
  /** Parsed CWL, for CWLWorkflowViewer. */
  cwl: Record<string, unknown>;
}
export interface CatalogueTool { id: string; name: string; type: AssayType }
export interface CatalogueDataset { id: string; name: string; category: Category }
export interface Catalogue {
  workflows: CatalogueWorkflow[];
  tools: CatalogueTool[];
  datasets: CatalogueDataset[];
}
