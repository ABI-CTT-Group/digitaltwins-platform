export interface DashboardCategory {
  seekId: string;
  name: string;
  category: string;
  description?: string;
  workflowSeekId?: string;
  tag?: string;
}

export interface DashboardWorkflow {
  uuid: string;
  seekId: string;
  name: string;
  type?: string;
  inputs?: IWorkflowInput[];
  outputs?: IWorkflowOutput[];
}

interface IWorkflowInput {
  input: { category: string; name: string; };
  datasetSelectedUuid: string;
  sampleSelectedType: string;
}
interface IWorkflowOutput {
  output: { category: string; name: string; },
  datasetName: string,
  sampleName: string
}

export interface SeekAssayDetails {
  seekId: string;
  name: string;
  relationships: {
    studySeekId: string;
    investigationSeekId: string;
  }
}

export interface AssayDetails {
  seekId: string;
  uuid: string;
  workflow: DashboardWorkflow;
  numberOfParticipants: Array<number>;
  isAssayReadyToLaunch: boolean;
}

export interface AssayLaunch {
  type?: string;
  data?: any;
  message?: string;
}

export interface AssayDataset {
  uuid: string;
  name: string;
}

export type SourceType = "github" | "gitlab" | "bitbucket" | "git_generic" | "local";

/** UI toggle state — Git URL (any provider) vs Local Folder. The actual
 *  `SourceType` for git is inferred from the URL host on blur. */
export type SourceMode = "git" | "local";

/** Reason codes returned by the backend probe-source endpoint. Drives the
 *  v-if expansion of token / auth-username / SSL-trust fields. */
export type ProbeFailureReason =
  | "auth_required"
  | "not_found"
  | "tls_error"
  | "network"
  | "rate_limit"
  | "validation"
  | "unknown";

/** Optional transient auth supplied at probe and at build/rebuild time.
 *  Never persisted server-side per phase-0.2 decision. */
export interface TransientAuth {
  token?: string;
  authUsername?: string;
  verifySsl?: boolean;
}

// Note: API request/response use camelCase here even though the backend
// schema is snake_case — the axios interceptor in http.ts deep-converts
// keys both directions (deepSnakeize on outgoing body/params, deepCamelize
// on incoming responses). Frontend code never sees snake_case.
export interface ProbeSourceRequest {
  sourceType: Exclude<SourceType, "local">;
  url: string;
  branch?: string;
  token?: string;
  authUsername?: string;
  verifySsl?: boolean;
}

export interface ProbeSourceSuccess {
  ok: true;
  data: {
    root: string;
    foldersInRoot: string[];
    packageVersion: string;
    packageAuthor: string;
    hasCwl: boolean;
    cwlRequired: boolean;
    /** Inlined when `hasCwl` is true so the annotation step can read the
     *  CWL without a second clone — backend reuses the shallow clone it
     *  already did for inspect. */
    cwlFile?: string;
    cwlContent?: string;
  };
}

export interface ProbeSourceFailure {
  ok: false;
  reason: ProbeFailureReason;
  message: string;
  providerHint?: string;
}

export type ProbeSourceResponse = ProbeSourceSuccess | ProbeSourceFailure;

export interface ToolInformationStep {
    name: string;
    version: string;
    repositoryUrl?: string;
    label: "GUI" | "Script";
    hasBackend: boolean;
    frontendFolder: string;
    frontendBuildCommand: string;
    backendFolder: string;
    backendDeployCommand: string;
    description?: string ;
    author?: string;
    toolMetadata: any;
    sourceType: SourceType;
    uploadId?: string;
}

export interface CheckNameResponse {
    available: boolean;
    message: string;
}
export interface ToolResponse {
    id: string
    toolMetadata: any
    name: string
    version: string
    label: string
    repositoryUrl: string
    frontendFolder: string
    frontendBuildCommand: string
    hasBackend: boolean
    backendFolder?: string
    backendDeployCommand: string
    description?: string
    author?: string
    status: string
    deployStatus?: string
    latestBuildId?: string
    latestDeployId?: string
    createdAt: string
    updatedAt: string
    sourceType?: SourceType
    localArchivePath?: string
}

export interface BuildResponse {
    id: string
    pluginId: string
    buildId: string
    status: string
    buildLogs?: string
    errorMessages?: string
    s3Path?: string
    createdAt: string
    updatedAt: string
}

export interface ToolDeployResponse {
    id: string
    pluginId: string
    buildId: string
    deployId: string
    status: string
    createdAt: string
    updatedAt: string
}

export interface ToolMinIOToolMetadata {
      uuid: string,
      id: string,
      name: string,
      path: string,
      expose: string,
      description: string,
      version: string,
      createdAt: string,
      author: string,
      repositoryUrl: string,
      isLocal: boolean,
      frontendFolder: string,
      hasBackend: boolean,
      backendFolder: string,
      backendDeployCommand: string,
      config: any
    }

export interface ToolMinIOMetadata {
    components: Array<ToolMinIOToolMetadata>
}

export interface ExcuteBuildResponse {
    buildId: string,
    status: string,
    message: string,
    repoUrl: string
}

export interface GitContent {
    name: string;
    path:string;
    download_url:string;
    git_url:string;
    html_url:string;
    sha:string;
    size:number;
    type:string;
    url:string;
    _links: {
        git:string;
        html:string;
        self:string;
    }
}

export interface WorkflowInformationStep {
    name: string;
    version: string;
    repositoryUrl?: string;
    description?: string ;
    author?: string;
    sourceType: SourceType;
    uploadId?: string;
}

export interface WorkflowResponse {
    id: string;
    name: string;
    version: string;
    repositoryUrl: string;
    description?: string;
    author?: string;
    status: string;
    latestBuildId?: string
    createdAt: string;
    updatedAt: string;
    sourceType?: SourceType;
    localArchivePath?: string;
}

interface AnnotateToolInput{
  name:string;
  resource: "Observation" | "ImagingStudy" | "DocumentReference" | ""
}
interface AnnotateToolOutput extends AnnotateToolInput{
  code: string; 
  system: string; 
  unit: string;
}

export interface AnnotateTool {
  name: string;
  inputs: Array<AnnotateToolInput>;
  outputs: Array<AnnotateToolOutput>;
}

export interface IAnnotation {
    fhirNote: string;
    sparcNote: string;
}

export interface AnnotationResponse {
  id:string;
  annotationId:string;
  fhirNote:string;
  sparcNote:string;
  createdAt:string;
  updatedAt:string;
}

export interface WorkflowStepAnnotation {
    id:string;
    uuid:string;
    name:string;
    toolFhirNote?:{
       [key:string]:any;
    };
}

export type BaseInformationStep = ToolInformationStep | WorkflowInformationStep;

// ---------------------------------------------------------------------------
// Measurements upload
// ---------------------------------------------------------------------------
//
// NOTE: `_auto` is a UI-only marker (set by the backend on /tree to hint which
// sample folder triggered the auto-classification). It MUST be recursively
// stripped before POSTing to `/api/measurement/{id}/annotation` — see
// `stripAuto` in `views/upload-dataset/measurements/components/`.
//
// uuid / endpointUrl / endpointUuid fields are MOCK values (prefix `MOCK-`)
// until digitaltwins-api integration lands. Treat them as read-only in the UI.

export type MeasurementStatus =
  | "pending"
  | "uploading"
  | "submit_failed"
  | "fhir_failed"
  | "completed";

export type MeasurementFailureStage =
  | "staging"
  | "fhir_build"
  | "upload"
  | "finalize"
  | "fhir_push";

export interface MeasurementInformationStep {
  name: string;
  description?: string;
  uploadId: string;
}

export interface MeasurementResponse {
  id: string;
  name: string;
  description?: string;
  uuid?: string;
  datasetPath?: string;
  exposeName?: string;
  s3Path?: string;
  status: MeasurementStatus | string;
  failureStage?: MeasurementFailureStage | string;
  failureMessage?: string;
  /** Whether a draft annotation exists — drives card menu button visibility.
   *  camelized from the backend's `has_annotation` by http.ts. */
  hasAnnotation?: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Response from `POST /api/measurement/upload-source`. */
export interface MeasurementSourceMeta {
  uploadId: string;
  patients: string[];
  samplesPerPatient: Record<string, string[]>;
  fileCountPerSample: Record<string, number>;
}

/** Tree node returned alongside descriptions on /tree. Loose shape — UI only
 *  consumes counts / labels, so we keep it as an open dict. */
export type MeasurementTreeNode = {
  name: string;
  type?: "dataset" | "patient" | "sample" | "file";
  children?: MeasurementTreeNode[];
  [k: string]: any;
};

/** Response from `GET /api/measurement/{id}/tree`. */
export interface MeasurementTreeResponse {
  tree: MeasurementTreeNode;
  descriptions: FhirCdaDescriptions;
  skippedSamples: string[];
}

/** UI-only auto-classification hint. Stripped before POST. */
export interface FhirCdaAutoMeta {
  samplePath?: string;
  sourceFile?: string;
  modality?: string;
  files?: string[];
}

export interface ObservationDescription {
  resourceType: "Observation";
  uuid: string;
  /** Quantity value (number) OR string value depending on `valueType`. */
  value?: number | string;
  /** "Quantity" | "String" — local-only UI tag, not part of FHIR shape. */
  valueType?: "Quantity" | "String";
  code: string;
  codeSystem: string;
  unit?: string;
  display?: string;
  _auto?: FhirCdaAutoMeta;
}

export interface DocumentAttachment {
  url: string;
  contentType: string;
  title?: string;
  size?: number;
}

export interface DocumentReferenceDescription {
  resourceType: "DocumentReference";
  uuid: string;
  description?: string;
  display?: string;
  attachments: DocumentAttachment[];
  _auto?: FhirCdaAutoMeta;
}

export interface ImagingStudySeries {
  uid?: string;
  endpointUrl: string;
  endpointUuid: string;
  name: string;
  numberOfInstances: number;
  bodySite?: string;
  instances: any[];
}

export interface ImagingStudyDescription {
  resourceType: "ImagingStudy";
  uuid: string;
  endpointUrl: string;
  description: string;
  display?: string;
  series: ImagingStudySeries[];
  _auto?: FhirCdaAutoMeta;
}

export interface FhirCdaPatient {
  uuid: string;
  name: string;
  observations: ObservationDescription[];
  imagingStudy: ImagingStudyDescription[];
  documentReference: DocumentReferenceDescription[];
}

export interface FhirCdaDescriptions {
  dataset: { uuid: string; name: string };
  patients: FhirCdaPatient[];
}

export interface MeasurementAnnotationResponse {
  id: string;
  measurementId: string;
  annotationId: string;
  descriptions?: FhirCdaDescriptions;
  createdAt: string;
  updatedAt: string;
}

export interface MeasurementDeleteResponse {
  status: boolean;
  message: string;
}
