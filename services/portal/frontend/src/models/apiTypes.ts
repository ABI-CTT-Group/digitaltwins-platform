import * as Copper from "copper3d";
import * as THREE from "three";

export interface INrrdCaseNames {
  names: string[];
  details: Array<IDetails>;
  [proName: string]: any;
}
export interface IDetails {
  name: string;
  masked: false;
  has_mesh: boolean;
  file_paths: {
    origin_nrrd_paths: string[];
    registration_nrrd_paths: string[];
    segmentation_breast_points_paths: string[];
    segmentation_breast_model_paths: string[];
    segmentation_manual_mask_paths: string[];
    segmentation_manual_3dobj_paths: string[];
  };
}
export interface IStoredMasks {
  label1: IExportMask[];
  label2: IExportMask[];
  label3: IExportMask[];
  hasData: false;
}
export interface IExportMask {
  caseId?: number;
  sliceIndex?: number;
  dataFormat?: string;
  width?: number;
  height?: number;
  voxelSpacing?: number[];
  spaceOrigin?: number[];
  data?: number[];
  [proName: string]: any;
}
export interface IExportMasks {
  caseId: string;
  masks: IStoredMasks;
}
export interface IReplaceMask {
  caseId: string;
  sliceId: number;
  label: string;
  mask: number[];
}
export interface ISaveSphere {
  caseId: string;
  sliceId: number;
  origin: number[];
  spacing: number[];
  sphereRadiusMM: number;
  sphereOriginMM: number[];
}
export interface ISaveTumourPosition {
  case_name: string;
  position: ICommXYZ;
  validate?: boolean;
}
export interface IMaskTumourObjData {
  maskTumourObjUrl?: string;
  meshVolume?: number;
}
export interface IParams {
  params: unknown;
  responseType?: string;
}
export interface ICaseUrls {
  nrrdUrls: Array<string>;
  jsonUrl?: string;
}
export interface ICaseRegUrls {
  nrrdUrls: Array<string>;
}
export interface ILoadUrls {
  [proName: string]: any;
}
export interface ICaseDetails {
  currentCaseId: string;
  details: Array<IDetails>;
  maskNrrd: string;
}

export interface ITumourCenterCaseDetails {
  currentCaseName: string;
  nrrdUrl: string;
  tumourWindow?: ITumourWindow;
  report?: ITumourStudyReport;
} 

export interface IRegRquest {
  name: string;
  radius?: number;
  origin?: number[];
}
export interface ILoadedMeshes {
  x: THREE.Mesh;
  y: THREE.Mesh;
  z: THREE.Mesh;
  order: number;
}

export interface ICommXYZ {
  x: number;
  y: number;
  z: number;
}

export interface ILeftRightData {
  maskNrrdMeshes: Copper.nrrdMeshesType;
  maskSlices: Copper.nrrdSliceType;
  url: string;
  register: boolean;
}
export interface INipplePoints {
  nodes: {
    right_nipple: number[];
    left_nipple: number[];
  };
  elements: {};
}

export interface IRibSkinPoints {
  Datapoints: number[][];
}

export interface ITumourWindow {
  bounding_box_max_point:{
    x:number;
    y:number;
    z:number
  },
  bounding_box_min_point:{
    x:number;
    y:number;
    z:number
  },
  center:{
    x:number;
    y:number;
    z:number
  }
}


export interface IRequests {
  url: string;
  params: any;
}

export interface IStudyDetails {
  position: ICommXYZ| null;
  distance: string;
  start: string | number;
  end: string | number;
  duration: string;
}

export interface ITumourStudyClockFace {
  face: "12:00" | "1:00" | "2:00" | "3:00" | "4:00" | "5:00" | "6:00" | "7:00" | "8:00" | "9:00" | "10:00" | "11:00" | "central";
  start: string | number;
  end: string | number;
  duration: string;
}

export interface ITumourStudyReport {
  nipple:IStudyDetails;
  skin: IStudyDetails;
  ribcage:IStudyDetails;
  clock_face: ITumourStudyClockFace;
  start: string | number;
  end: string | number;
  total_duration: string;
  spacing: ICommXYZ | null;
  origin: ICommXYZ | null;
  complete: boolean;
  assisted: boolean;
}

export interface ITumourStudyAssisted {
  tumour_position: ISaveTumourPosition;
  tumour_study_report: ITumourStudyReport;
}

export interface ITumourStudyWindow {
  bounding_box_max_point: ICommXYZ;
  bounding_box_min_point: ICommXYZ;
  center: ICommXYZ;
  validate: boolean;
}

export interface ITumourStudyAppDetail {
  name: string;
  file_path: string;
  tumour_window: ITumourStudyWindow;
  report: ITumourStudyReport;
}

export interface ITumourStudyAppDetails {
  details: ITumourStudyAppDetail[];
}

export interface IKeyboardSettings {
  draw: string;
  undo: string;
  contrast: string[];
  crosshair: string;
  mouseWheel: "Scroll:Zoom" | "Scroll:Slice" | string;
  [key: string]: any;
}

export interface ILeftCoreCopperInit { 
  appRenderer: Copper.copperRenderer; 
  nrrdTools: Copper.NrrdTools; 
  scene: Copper.copperScene 
}

export interface IToolSphereData {
  sphereOrigin: number[];
  sphereRadius: number;
}
export interface IToolMaskData {
  image: ImageData;
  sliceId: number;
  label: string;
  width: number;
  height: number;
  clearAllFlag?: boolean;
}
export interface IToolCalculateSpherePositionsData {
  tumourSphereOrigin: Copper.ICommXYZ | null;
  skinSphereOrigin: Copper.ICommXYZ | null;
  ribSphereOrigin: Copper.ICommXYZ | null;
  nippleSphereOrigin: Copper.ICommXYZ | null;
  aix: "x" | "y" | "z";
}
export interface IToolAfterLoadImagesResponse {
  allSlices: any[];
  allLoadedMeshes: ILoadedMeshes[];
}
export interface IToolGetSliceNumber {
  index: number;
  contrastindex: number;
}
export interface IToolGetMouseDragContrastMove {
  step:number, 
  towards:"horizental"|"vertical"
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

export interface IAssayDetails {
  seekId: string;
  uuid: string;
  workflow: {
    uuid: string;
    seekId: string;
    inputs: IWorkflowInput[];
    outputs: IWorkflowOutput[];
  };
  numberOfParticipants: number|string;
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