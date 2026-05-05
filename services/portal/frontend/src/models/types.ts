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

export type SourceType = "github" | "local";

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
