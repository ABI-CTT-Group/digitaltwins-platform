
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
    repository_url: string
    frontend_folder: string
    frontend_build_command: string
    has_backend: boolean
    backend_folder?: string
    backend_deploy_command: string
    description?: string
    author?: string
    status: string
    created_at: string
    updated_at: string
    [key:string]:any
}

export interface PluginBuildResponse {
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

export interface PluginExcuteBuildResponse {
    build_id: string,
    status: string,
    message: string,
    repo_url: string
}