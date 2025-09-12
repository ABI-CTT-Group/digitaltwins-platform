
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
    created_at: string
    updated_at: string
    [key:string]:any
}