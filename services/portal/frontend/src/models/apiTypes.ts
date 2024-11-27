import * as Copper from "copper3d";
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
export interface IMaskMesh {
  maskMeshObjUrl?: string;
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
export interface ISliceIndex {
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
