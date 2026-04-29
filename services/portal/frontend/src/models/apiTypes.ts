export interface IDashboardCategory {
  seekId: string;
  name: string;
  category: string;
  description?: string;
  workflow_seek_id?: string;
  tag?: string;
}

export interface IDashboardWorkflow {
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

export interface ISeekAssayDetails {
  seekId: string;
  name: string;
  relationships: {
    studySeekId: string;
    investigationSeekId: string;
  }
}

export interface IAssayDetails {
  seekId: string;
  uuid: string;
  workflow: IDashboardWorkflow;
  numberOfParticipants: Array<number>;
  isAssayReadyToLaunch: boolean;
}

export interface IAssayLaunch {
  type?: string;
  data?: any;
  message?: string;
}

export interface IAssayDataset {
  uuid: string;
  name: string;
}

