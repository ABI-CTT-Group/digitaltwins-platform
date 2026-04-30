export interface DashboardCategory {
  seekId: string;
  name: string;
  category: string;
  description?: string;
  workflow_seek_id?: string;
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
  datasetSelectedUUID: string;
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

export interface ToolInformationStep {
    name: string;
    version: string;
    repository_url: string;
    label: "GUI" | "Script";
    has_backend: boolean;
    frontend_folder: string;
    frontend_build_command: string;
    backend_folder: string;
    backend_deploy_command: string;
    description?: string ;
    author?: string;
    plugin_metadata: any;
}

export interface CheckNameResponse {
    available: boolean;
    message: string;
}
export interface ToolResponse {
    id: string
    plugin_metadata: any
    name: string
    version: string
    label: string
    repository_url: string
    frontend_folder: string
    frontend_build_command: string
    has_backend: boolean
    backend_folder?: string
    backend_deploy_command: string
    description?: string
    author?: string
    status: string
    deploy_status?: string
    latest_build_id?: string
    latest_deploy_id?: string
    created_at: string
    updated_at: string
}

export interface BuildResponse {
    id: string
    plugin_id: string
    build_id: string
    status: string
    build_logs?: string
    error_messages?: string
    s3_path?: string
    created_at: string
    updated_at: string
}

export interface ToolDeployResponse {
    id: string
    plugin_id: string
    build_id: string
    deploy_id: string
    status: string
    created_at: string
    updated_at: string
}

export interface ToolMinIOToolMetadata {
      uuid: string,
      id: string,
      name: string,
      path: string,
      expose: string,
      description: string,
      version: string,
      created_at: string,
      author: string,
      repository_url: string,
      is_local: boolean,
      frontend_folder: string,
      has_backend: boolean,
      backend_folder: string,
      backend_deploy_command: string,
      config: any
    }

export interface ToolMinIOMetadata {
    components: Array<ToolMinIOToolMetadata>
}

export interface ExcuteBuildResponse {
    build_id: string,
    status: string,
    message: string,
    repo_url: string
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
    repository_url: string;
    description?: string ;
    author?: string;
}

export interface WorkflowResponse {
    id: string;
    name: string;
    version: string;
    repository_url: string;
    description?: string;
    author?: string;
    status: string;
    latest_build_id?: string
    created_at: string;
    updated_at: string;
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
    fhir_note: string;
    sparc_note: string;
}

export interface AnnotationResponse {
  id:string;
  annotation_id:string;
  fhir_note:string;
  sparc_note:string;
  created_at:string;
  updated_at:string;
}

export interface WorkflowStepAnnotation {
    id:string;
    uuid:string;
    name:string;
    tool_fhir_note?:{
       [key:string]:any;
    };
}

export type BaseInformationStep = ToolInformationStep | WorkflowInformationStep;
