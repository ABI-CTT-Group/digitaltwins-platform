
export interface IStudy {
    name: string;
    subTitle: string;
    description: string;
    src: string;
    status: string;
    isEnter: boolean;
    session: string;
}
  
export interface IBaseCategory {
    category: string;
    name: string;
    description?: string;
}

export interface ICategoryNode extends IBaseCategory {
    children: (ICategoryNode | IStudiesNode)[];
}

export interface IStudiesNode {
    studies: IStudy[];
}

export type IDashboardData = ICategoryNode[];

export interface IWorkflowData {
    uuid: string;
    name: string;
    type: string;
    inputs?: string[];
    outputs?: string[];
}
export interface IToolInformationStep {
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
export interface PluginResponse {
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
    [key:string]:any
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

export interface PluginDeployResponse {
    id: string
    plugin_id: string
    build_id: string
    deploy_id: string
    status: string
    created_at: string
    updated_at: string
}

export interface PluginMinIOToolMetadata {
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

export interface PluginMinIOMetadata {
    components: Array<PluginMinIOToolMetadata>
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

export interface IWorkflowInformationStep {
    name: string;
    version: string;
    repository_url: string;
    description?: string ;
    author?: string;
}

export interface IWrokflowResponse {
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
    [key:string]:any;
}

interface IAnnotateToolInput{
  name:string;
  resource: "Observation" | "ImagingStudy" | "DocumentReference" | ""
}
interface IAnnotateToolOutput extends IAnnotateToolInput{
  code: string; 
  system: string; 
  unit: string;
}

export interface IAnnotateTool {
  name: string;
  inputs: Array<IAnnotateToolInput>;
  outputs: Array<IAnnotateToolOutput>;
}

export interface IAnnotation {
    fhir_note: string;
    sparc_note: string;
}

export interface IAnnotationResponse {
  id:string;
  annotation_id:string;
  fhir_note:string;
  sparc_note:string;
  created_at:string;
  updated_at:string;
}

export interface IWorkflowStepAnnotation {
    id:string;
    uuid:string;
    name:string;
    tool_fhir_note?:{
       [key:string]:any; 
    };
}
