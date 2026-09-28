import * as Copper from "copper3d";
import * as THREE from "three";

export interface IRequests {
  url: string;
  params: any;
}

export interface IDashboardCategory {
  uuid: string;
  seekId: string;
  name: string;
  category: string;
  description: string;
}

export interface IDashboardWorkflow {
  uuid: string;
  seekId: string;
  name: string;
  type: string;
  inputs?: { category: string; name: string; }[];
  outputs?: { category: string; name: string; }[];
  origin?: any;
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
  workflow: {
    uuid: string;
    seekId: string;
    inputs: IWorkflowInput[];
    outputs: IWorkflowOutput[];
  };
  numberOfParticipants: Array<number>;
  isAssayReadyToLaunch: boolean;
}

export interface IAssayLaunch {
  type: string;
  data: any;
}

export interface IAssayDataset {
  uuid: string;
  name: string;
}

export interface IClinicalReportViewerDetail{
  uuid: string;
  date: string;
}

export interface IProjectDetail{
  seekId: string;
  title: string
}

export interface IDashboardAuth{
  username: string;
  password: string;
}

export interface IDashboardAuthResponse{
  access_token: string;
}