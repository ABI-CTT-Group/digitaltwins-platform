
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
    sourceUrl: string;
    pluginName: string;
    author: string;
    version: string;
    description: string;
    frontendFolderName: string;
    frontendBuildCommand: string;
    hasbackend: boolean;
    backendFolderName: string;
    backendBuildCommand: string;
}