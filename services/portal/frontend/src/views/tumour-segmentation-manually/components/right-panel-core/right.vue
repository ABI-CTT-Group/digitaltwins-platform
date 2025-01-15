<template>
  <RightPanelCore
    ref="rightPanelCoreRef"
    :show-bottom-nav-bar="panelWidth >= 410 ? true : false"
    :show-loading-animation="openLoading"
    @finished-copper-init="onFinishedCopperInit"
  >
    <template #tumour-distance-panel>
      <TumourDistancePanelRight 
        :tumour-volume="tumourVolume"
        :tumour-extent="tumourExtent"
        :skin-dist="skinDist"
        :rib-dist="ribDist"
        :nipple-dist="nippleDist"
        :nipple-clock="nippleClock"
      />
    </template>
    <template #bottom-nav-bar>
      <NavBarRight
        :panel-width="Math.ceil(panelWidth) "
        @on-view-single-click="handleViewSigleClick"
        @on-view-double-click="handleViewsDoubleClick"
      />
    </template>
  </RightPanelCore>
</template>

<script setup lang="ts">
import RightPanelCore from "@/components/view-components/RightPanelCore.vue";
import Drawer from "@/components/commonBar/drawer.vue";
import TumourDistancePanelRight from "@/components/view-components/TumourDistancePanelRight.vue";
import NavBarRight from "@/components/commonBar/NavBarRight.vue";
import { GUI } from "dat.gui";
import * as THREE from "three";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
import createKDTree from "copper3d-tree";
// import * as Copper from "@/ts/index";
import {
  onMounted,
  ref,
  watch,
  onUnmounted
} from "vue";
import emitter from "@/plugins/custom-emitter";;
import { storeToRefs } from "pinia";
import {
  useMaskNrrdStore,
  useMaskTumourObjStore,
  useBreastMeshObjStore,
  useNipplePointsStore,
  useRibPointsStore,
  useSkinPointsStore
} from "@/store/app";
import {
  ICaseDetails,
  ICommXYZ,
  ILeftRightData,
  INipplePoints,
  IRibSkinPoints,
  ISaveSphere
} from "@/models/apiTypes";
import {
  findCurrentCase,
  transformMeshPointToImageSpace,
  getClosestNipple,
  createOriginSphere
} from "@/plugins/view-utils/tools";
import { PanelOperationManager, valideClock, deepClone, processPointsCloud } from "@/plugins/view-utils/utils-right";
import loadingGif from "@/assets/loading.svg";
import { switchAnimationStatus } from "@/components/view-components/leftCoreUtils";


type Props = {
  panelWidth?: number;
};
let rightPanelCoreRef = ref<InstanceType<typeof RightPanelCore>>();
let baseContainer: HTMLDivElement | undefined;
let guiContainer: HTMLDivElement | undefined;
let loadingContainer: HTMLDivElement | undefined;;
let progress: HTMLDivElement | undefined;
let copperLoadingAnimationForNrrdLoader: Copper.loadingBarType | undefined;

let panelOperator: PanelOperationManager;
let copperScene: Copper.copperScene;


let currentCasename = ref<string>("");

let socket = new WebSocket("ws://127.0.0.1:8000/ws");
let socketTimer: NodeJS.Timer;

// for deal with single/double click on a div
let clickCount = 0;
let clickTimer: any = null;
let validFlag = false;

// Right panel display state
const openLoading = ref(false);
const tumourVolume = ref(0);
const tumourExtent = ref(0);
const skinDist = ref("0");
const ribDist = ref("0");
const nippleDist = ref("L: 0");
const nippleClock = ref("@ 0:0");

let allRightPanelMeshes: Array<THREE.Object3D> = [];
let loadNrrdMeshes: Copper.nrrdMeshesType;
let loadNrrdSlices: Copper.nrrdSliceType;

let nippleCentralLimit = 10;
let nippleTl: number[] = [];
let nippleTr: number[] = [];
let tumourSliceIndex: ICommXYZ = {x:0, y:0, z:0};


// the nrrd origin + bais for display tumour, breast model, skin, ribcage, nipple
let correctOrigin = [0,0,0];
let nrrdOrigin:number[] = []
let nrrdSpacing:number[] = [];
let nrrdRas:number[] = []; // mm
let nrrdDimensions:number[] = []; // pixels
let nrrdBias:THREE.Vector3 = new THREE.Vector3(0,0,0);

let preTumourShpere:THREE.Mesh | undefined = undefined;

let skinTree:any;
let ribTree:any;
let processedSkinPoints:number[][] = []
let processedRibPoints:number[][] = []

let segementTumour3DModel:THREE.Group|THREE.Mesh|undefined = undefined;
let breast3DModel:THREE.Group|undefined;
let registrationMeshes: Copper.nrrdMeshesType | undefined;
let originMeshes: Copper.nrrdMeshesType | undefined;
let registrationSlices: Copper.nrrdSliceType | undefined;
let originSlices: Copper.nrrdSliceType | undefined;

let tumourPosition:THREE.Vector3|undefined = undefined
const skinPosition:THREE.Vector3 = new THREE.Vector3(0,0,0)
const ribPosition:THREE.Vector3 = new THREE.Vector3(0,0,0)

const commGeo = new THREE.SphereGeometry(3, 32, 16)

const material = new THREE.MeshBasicMaterial({ color: "hotpink" });
const nippleSphereL = new THREE.Mesh(commGeo, material);
const nippleSphereR = new THREE.Mesh(commGeo, material);
const skinSphere = new THREE.Mesh(commGeo, new THREE.MeshBasicMaterial({ color: "#FFFF00"}));
const ribSphere = new THREE.Mesh(commGeo, new THREE.MeshBasicMaterial({ color: "#00E5FF" }));
skinSphere.renderOrder=0;
ribSphere.renderOrder=0;

const { maskNrrd } = storeToRefs(useMaskNrrdStore());
const { getMaskNrrd } = useMaskNrrdStore();
const { maskTumourObj } = storeToRefs(useMaskTumourObjStore());
const { getMaskTumourObj } = useMaskTumourObjStore();
const { breastMeshObj } = storeToRefs(useBreastMeshObjStore());
const { getBreastMeshObj } = useBreastMeshObjStore();
const { nipplePoints } = storeToRefs(useNipplePointsStore());
const { getNipplePoints } = useNipplePointsStore();
const { skinPoints } = storeToRefs(useSkinPointsStore());
const { getSkinPoints } = useSkinPointsStore();
const { ribPoints } = storeToRefs(useRibPointsStore());
const { getRibPoints } = useRibPointsStore();

const props = withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

watch(()=>props.panelWidth, (newVal, oldVal) => {
  copperScene?.onWindowResize();
});

// App entry

onMounted(() => {
  baseContainer = rightPanelCoreRef.value?.baseContainer;
  loadingContainer = rightPanelCoreRef.value?.loadingContainer;
  guiContainer = rightPanelCoreRef.value?.guiContainer;
  progress = rightPanelCoreRef.value?.progress;
  copperLoadingAnimationForNrrdLoader = rightPanelCoreRef.value?.copperLoadingAnimationForNrrdLoader;
  manageEmitters();
  initSocket()

});

function initSocket(){
  socket.onopen = function (e) {
    console.log("socket send...");
    socket.send("Frontend socket connect!");
  };

  socket.onmessage = function (event) {
    if (typeof event.data === "string") {
      if (event.data === "delete") {
        tumourVolume.value = 0;
        if (!!segementTumour3DModel) copperScene.scene.remove(segementTumour3DModel);
        segementTumour3DModel = undefined;

        copperScene.scene.remove(ribSphere);
        copperScene.scene.remove(skinSphere);

        initPanelValue();
      } else {
        const volumeJson = JSON.parse(event.data);
        tumourVolume.value = Math.ceil(volumeJson.volume) / 1000;
      }
      clearInterval(socketTimer as NodeJS.Timeout);
    } else {
      if(!!maskTumourObj.value.maskTumourObjUrl){
        console.log("remove old mesh");
        
        URL.revokeObjectURL(maskTumourObj.value.maskTumourObjUrl)
      }
      const blob = new Blob([event.data], { type: "model/obj" });
      const url = URL.createObjectURL(blob);
      maskTumourObj.value.maskTumourObjUrl = url;

      if(!!preTumourShpere){
        (copperScene as Copper.copperScene).scene.remove(preTumourShpere);
        preTumourShpere = undefined;
      }
      
      loadSegmentTumour(url)
      switchAnimationStatus(loadingContainer!, progress!, "none");
    }
    openLoading.value = false;
  };
}

function initPanelValue() {
  tumourVolume.value = 0;
  tumourExtent.value = 0;
  skinDist.value = "0";
  ribDist.value = "0";
  nippleDist.value = "L 0";
  nippleClock.value = "@ 0:0";
}

function onFinishedCopperInit(data: { appRenderer: Copper.copperRenderer, copperScene: Copper.copperScene, panelOperator: PanelOperationManager }) {
  copperScene = data.copperScene;
  panelOperator = data.panelOperator;

}

function requestSocketUpdateTumourModel() {
  const intervalId = setInterval(() => {
    socket.send("Frontend socket connect!");
  }, 1000);
  return intervalId;
}

function clearModelsAndStates(){
  registrationMeshes = undefined;
  originMeshes = undefined;
  registrationSlices = undefined;
  originSlices = undefined;
  segementTumour3DModel = undefined;
  breast3DModel = undefined;
  preTumourShpere = undefined;
  tumourSliceIndex = {x:0, y:0, z:0};
  !!skinTree?skinTree.dispose():null;
  !!ribTree?ribTree.dispose():null;
  skinTree = undefined;
  ribTree = undefined;
  initPanelValue();
  removeOldMeshes(allRightPanelMeshes);
  if(!!maskTumourObj.value.maskTumourObjUrl){
      URL.revokeObjectURL(maskTumourObj.value.maskTumourObjUrl)
  }
}


function manageEmitters() {
  /**
   * UI Control layer
   * */ 
  emitter.on("Common:ResizeCopperSceneWhenNavChanged", emitterOnResizeCopperSceneWhenNavChanged);
  /**
   * Logic layer
   * */ 
  // switch cases, dream start area
  emitter.on("Segmentation:CaseDetails", emitterOnCaseDetails);
  // switch segmented tumour mesh 3D obj model
  emitter.on("Segmentation:SyncTumourModelButtonClicked", emitterOnSyncTumourModelButtonClicked);
  // Listen to switch register images and origin images
  emitter.on("Segmentation:RegisterButtonStatusChanged", emitterOnRegisterButtonStatusChanged);
  // When left panel draw sphere, then the right panel need automatically update the sphere tumour
  emitter.on("SegmentationTrial:DrawSphereFunction", emitterOnDrawSphereFunction)
  // When nav bar toggle breast visibility
  emitter.on("Common:ToggleBreastVisibility", emitterOnToggleBreastVisibility)
}

const emitterOnResizeCopperSceneWhenNavChanged = () => {
  // give a 300ms delay for wait right panel to recalculate width, then update threejs
  setTimeout(() => {
    copperScene?.onWindowResize();
  }, 300);
}
const emitterOnCaseDetails = async (caseDetails: ICaseDetails) => {
  // 1. clear previous meshes and clear state
  clearModelsAndStates()
  // 2. request data
  const case_infos: ICaseDetails = caseDetails;
  const case_detail = findCurrentCase(
    case_infos.details,
    case_infos.currentCaseId
  );
  // 2.1 Get currentCasename and get the init data
  await getInitDataOnceCaseSwitched(caseDetails);

  // 2.2 Load Nrrd
  loadNrrd(maskNrrd.value as string, "register")?.then(async (nrrdData)=>{
    if(!!skinPoints.value){
      const skinPointCloud = skinPoints.value as IRibSkinPoints
      processedSkinPoints = processPointsCloud(skinPointCloud["Datapoints"] as number[][], nrrdData.bias)
      skinTree = createKDTree(processedSkinPoints);
    }
    if(!!ribPoints.value){
      const ribPointCloud = ribPoints.value as IRibSkinPoints
      processedRibPoints = processPointsCloud(ribPointCloud["Datapoints"] as number[][], nrrdData.bias)
      ribTree = createKDTree(processedRibPoints);
    }
    // 2.3 Load breast model, nipple, skin, ribcage, 3d model
    loadBreastModel()
    // 2.4 Load tumour obj model if has
    if(!!maskTumourObj.value){
      tumourVolume.value = Math.ceil(maskTumourObj.value.meshVolume as number) / 1000;
      // maskMeshObj.value.maskMeshObjUrl as string
      // 2.4 load tumour model
      loadSegmentTumour(maskTumourObj.value.maskTumourObjUrl as string)
    }else{
      requestUpdateSliderSettings();
    }
  });
}

const emitterOnSyncTumourModelButtonClicked = () => {
  switchAnimationStatus(loadingContainer!, progress!, "flex");
  openLoading.value = true;
  socketTimer = requestSocketUpdateTumourModel();
}
const emitterOnRegisterButtonStatusChanged = (data: ILeftRightData) => {
  const res = data;
  // removeOldMeshes([nrrdMeshes.x, nrrdMeshes.y, nrrdMeshes.z]);

  const recordSliceIndex = {
    x: loadNrrdSlices.x.index,
    y: loadNrrdSlices.y.index,
    z: loadNrrdSlices.z.index,
  };
  
  if (originMeshes === undefined && originSlices === undefined) {
    copperScene.loadNrrd(
      res.url,
      copperLoadingAnimationForNrrdLoader!,
      true,
      (
        volume: any,
        nrrdMesh: Copper.nrrdMeshesType,
        nrrdSlices: Copper.nrrdSliceType
      ) => {
        nrrdMesh.x.name = "origin sagittal";
        nrrdMesh.y.name = "origin coronal";
        nrrdMesh.z.name = "origin axial";
        originMeshes = nrrdMesh;
        originSlices = nrrdSlices;
        allRightPanelMeshes.push(
          ...[originMeshes.x, originMeshes.y, originMeshes.z]
        );
        if (registrationMeshes)
          copperScene.scene.remove(
            ...[
              registrationMeshes.x,
              registrationMeshes.y,
              registrationMeshes.z,
            ]
          );

        loadNrrdMeshes = originMeshes as Copper.nrrdMeshesType;
        loadNrrdSlices = originSlices as Copper.nrrdSliceType;

        resetSliceIndex(recordSliceIndex);
        copperScene.scene.add(
          ...[loadNrrdMeshes.x, loadNrrdMeshes.y, loadNrrdMeshes.z]
        );
      }
    );
  } else {
    if (res.register) {
      if (originMeshes)
        copperScene.scene.remove(
          ...[originMeshes.x, originMeshes.y, originMeshes.z]
        );
      loadNrrdMeshes = registrationMeshes as Copper.nrrdMeshesType;
      loadNrrdSlices = registrationSlices as Copper.nrrdSliceType;
    } else {
      if (registrationMeshes)
        copperScene.scene.remove(
          ...[
            registrationMeshes.x,
            registrationMeshes.y,
            registrationMeshes.z,
          ]
        );
      loadNrrdMeshes = originMeshes as Copper.nrrdMeshesType;
      loadNrrdSlices = originSlices as Copper.nrrdSliceType;
    }
    resetSliceIndex(recordSliceIndex);
    copperScene.scene.add(
      ...[loadNrrdMeshes.x, loadNrrdMeshes.y, loadNrrdMeshes.z]
    );
  }
}
const emitterOnDrawSphereFunction = (val: ISaveSphere)=>{
  if(!!preTumourShpere){
    copperScene.scene.remove(preTumourShpere)
    preTumourShpere = undefined;
  }
  if(!!segementTumour3DModel){
    copperScene.scene.remove(segementTumour3DModel);
  }

  const sphereData = val;
  const geometry = new THREE.SphereGeometry(sphereData.sphereRadiusMM, 32, 16);
  const material = new THREE.MeshBasicMaterial({ color: "#228b22" });

  const sphereTumour = new THREE.Mesh(geometry, material);
  const spherePosition = [correctOrigin[0]+sphereData.sphereOriginMM[0], correctOrigin[1]+sphereData.sphereOriginMM[1], correctOrigin[2]+sphereData.sphereOriginMM[2]]

  sphereTumour.position.set(spherePosition[0], spherePosition[1],spherePosition[2])
  if (!tumourPosition) {
    tumourPosition = new THREE.Vector3()
  }
  tumourPosition?.set(spherePosition[0], spherePosition[1],spherePosition[2])

  // update tumour size
  tumourVolume.value =  Number(((4/3) * Math.PI * Math.pow(sphereData.sphereRadiusMM, 3)/1000).toFixed(3));


  loadNrrdSlices.x.index = (tumourSliceIndex as ICommXYZ).x =
  loadNrrdSlices.x.RSAMaxIndex / 2 + sphereTumour.position.x;
  loadNrrdSlices.y.index = (tumourSliceIndex as ICommXYZ).y =
  loadNrrdSlices.y.RSAMaxIndex / 2 + sphereTumour.position.y;
  loadNrrdSlices.z.index = (tumourSliceIndex as ICommXYZ).z =
  loadNrrdSlices.z.RSAMaxIndex / 2 + sphereTumour.position.z;
  loadNrrdSlices.x.repaint.call(loadNrrdSlices.x);
  loadNrrdSlices.y.repaint.call(loadNrrdSlices.y);
  loadNrrdSlices.z.repaint.call(loadNrrdSlices.z);
  copperScene.scene.add(sphereTumour);

  preTumourShpere = sphereTumour;
  allRightPanelMeshes.push(sphereTumour);

  // get closest point
  displayAndCalculateNSR();
}
const emitterOnToggleBreastVisibility = (val: boolean)=>{
  if (!!breast3DModel){
    breast3DModel.traverse((child)=>{
      if((child as THREE.Mesh).isMesh){
        child.visible = val;
      }
    })
  }
}


const getInitDataOnceCaseSwitched = async (caseDetails: ICaseDetails)=>{
  
  currentCasename.value = caseDetails.currentCaseId;
  // get mask nrrd blob url
  maskNrrd.value = caseDetails.maskNrrd;
  // get mask tumour obj url
  await getMaskTumourObj(currentCasename.value);
  // get breast mesh obj url
  await getBreastMeshObj(currentCasename.value);
  // get ribcage points
  await getRibPoints(currentCasename.value);
  // get skin points
  await getSkinPoints(currentCasename.value);
  // get nipple points
  await getNipplePoints(currentCasename.value);
}

/**
 * load the nrrd case, calculate the nrrd image origin, spacing, ras, dimensions, bias for load nipple, breast model
 * get the nrrd meshes and slices
 * @param nrrdUrl nrrd case url
 * @param name "register"|"origin"
 */
function loadNrrd(nrrdUrl: string, name:"register"|"origin") {
  
  if (copperScene === undefined) {
    console.log("copperScene is missing!");
    return;
  }
 
  // remove GUI
  const opts: Copper.optsType = {
    openGui: false,
    // container: baseContainer_gui.value,
  };
  
  return new Promise<{ origin: number[], spacing: number[],  ras: number[], dimensions:number[], bias: THREE.Vector3}>((resolve, reject) => {
    const nrrdCallback = async (
    volume: any,
    nrrdMesh: Copper.nrrdMeshesType,
    nrrdSlices: Copper.nrrdSliceType,
    gui?: GUI
  ) => {
    // adjust nrrd volume contrast windowHigh and windowLow
    // volume.windowHigh = 2000;
    // volume.windowLow = 82;
    // volume.repaintAllSlices();

    nrrdOrigin = volume.header.space_origin.map((num: any) => Number(num));
    nrrdSpacing = volume.spacing;
    nrrdRas = volume.RASDimensions; // mm
    nrrdDimensions = volume.dimensions; // pixels

    const x_bias = -(nrrdOrigin[0] * 2 + nrrdRas[0]) / 2;
    const y_bias = -(nrrdOrigin[1] * 2 + nrrdRas[1]) / 2;
    const z_bias = -(nrrdOrigin[2] * 2 + nrrdRas[2]) / 2;

    nrrdBias = new THREE.Vector3(x_bias, y_bias, z_bias);
    correctOrigin = [
          nrrdOrigin[0] + x_bias,
          nrrdOrigin[1] + y_bias,
          nrrdOrigin[2] + z_bias,
        ];  

    // const a = createOriginSphere(origin,ras,spacing,x_bias,y_bias,z_bias);
    // copperScene.scene.add(...a)

    if(name==="register"){
      loadNrrdMeshes = registrationMeshes = nrrdMesh;
      loadNrrdSlices = registrationSlices = nrrdSlices;
    }else{
      loadNrrdMeshes = originMeshes = nrrdMesh;
      loadNrrdSlices = originSlices = nrrdSlices;
    }
  
    loadNrrdSlices.x.index = Math.ceil(loadNrrdSlices.x.RSAMaxIndex / 2);
    loadNrrdSlices.y.index = Math.ceil(loadNrrdSlices.y.RSAMaxIndex / 2);
    loadNrrdSlices.z.index = Math.ceil(loadNrrdSlices.z.RSAMaxIndex / 2);

    loadNrrdSlices.x.repaint.call(loadNrrdSlices.x);
    loadNrrdSlices.y.repaint.call(loadNrrdSlices.y);
    loadNrrdSlices.z.repaint.call(loadNrrdSlices.z);
    
    nrrdMesh.x.name = "Sagittal";
    nrrdMesh.y.name = "Cornal";
    nrrdMesh.z.name = "Axial";
    copperScene.addObject(nrrdMesh.x);
    copperScene.addObject(nrrdMesh.y);
    copperScene.addObject(nrrdMesh.z);

    allRightPanelMeshes.push(nrrdMesh.x, nrrdMesh.y, nrrdMesh.z);

    !!resolve && resolve({ origin: nrrdOrigin, spacing: nrrdSpacing,  ras: nrrdRas, dimensions:nrrdDimensions, bias: nrrdBias});
    // reset view
    resetNrrdImage();
  };

  (copperScene as Copper.copperScene).loadNrrd(
    nrrdUrl,
    copperLoadingAnimationForNrrdLoader!,
    true,
    nrrdCallback,
    opts
  );
  })

}

function requestUpdateSliderSettings(){
  const sliderSettingsValue = {
        panelOperator,
        dimensions:nrrdDimensions,
        spacing: nrrdSpacing, 
        currentValue:[
          Math.ceil(loadNrrdSlices.x.index / nrrdSpacing[0]),
          Math.ceil(loadNrrdSlices.y.index / nrrdSpacing[1]),
          Math.ceil(loadNrrdSlices.z.index / nrrdSpacing[2])
        ]} 
  emitter.emit("SegmentationTrial:RightPanelSliderSettingValueUpdated", sliderSettingsValue)
}

async function loadBreastModel() {

  //  todo load nipple data
  const nippleResult = !!nipplePoints.value;

  if (nippleResult) {
    const nipples = nipplePoints.value as INipplePoints;
    const l = nipples.nodes.left_nipple;
    const r = nipples.nodes.right_nipple;
    const nipplesPos = [l, r];

    nippleTl = transformMeshPointToImageSpace(
      nipplesPos[0],
      nrrdOrigin,
      nrrdSpacing,
      nrrdDimensions,
      nrrdBias
    );
    nippleTr = transformMeshPointToImageSpace(
      nipplesPos[1],
      nrrdOrigin,
      nrrdSpacing,
      nrrdDimensions,
      nrrdBias
    );

    // valide(tl,tr,nrrdMesh)
    nippleSphereL.position.set(nippleTl[0], nippleTl[1], nippleTl[2]);
    nippleSphereR.position.set(nippleTr[0], nippleTr[1], nippleTr[2]);

    copperScene.addObject(nippleSphereR);
    copperScene.addObject(nippleSphereL);

    allRightPanelMeshes.push(nippleSphereL);
    allRightPanelMeshes.push(nippleSphereR);
  }

  // load breast model

  if(!!breastMeshObj.value){
    copperScene.loadOBJ(breastMeshObj.value as string, (content) => {
      breast3DModel = content
      allRightPanelMeshes.push(content);
      content.position.set(nrrdBias.x, nrrdBias.y, nrrdBias.z);
      content.renderOrder = 3;
      content.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            (child as THREE.Mesh).renderOrder=3;
            (child as THREE.Mesh).material = new THREE.MeshBasicMaterial({
              side: THREE.DoubleSide,
              // wireframe:true,
              // depthWrite:false,
              transparent:true,
              opacity:0.2,
              color: "#795548",
            });
          }
        });
    })
  }
}

function loadSegmentTumour(tomourUrl:string){
  preTumourShpere = undefined;
  if(!!segementTumour3DModel){
    copperScene.scene.remove(segementTumour3DModel);
    segementTumour3DModel = undefined;
  }

  copperScene.loadOBJ(tomourUrl, (content) => {

  allRightPanelMeshes.push(content);

  segementTumour3DModel = content;


  content.position.set(nrrdBias.x, nrrdBias.y, nrrdBias.z);
  const tumourMesh = content.children[0] as THREE.Mesh;
  const tumourMaterial =
    tumourMesh.material as THREE.MeshStandardMaterial;
  // tumourMaterial.color = new THREE.Color("green");

  tumourMesh.renderOrder = 3;

  const box = new THREE.Box3().setFromObject(content);
  const size = box.getSize(new THREE.Vector3()).length();

  tumourPosition = box.getCenter(new THREE.Vector3());
  // reset nrrd slice

  loadNrrdSlices.x.index = loadNrrdSlices.x.RSAMaxIndex / 2 + tumourPosition.x;
  loadNrrdSlices.y.index = loadNrrdSlices.y.RSAMaxIndex / 2 + tumourPosition.y;
  loadNrrdSlices.z.index = loadNrrdSlices.z.RSAMaxIndex / 2 + tumourPosition.z;
  loadNrrdSlices.x.repaint.call(loadNrrdSlices.x);
  loadNrrdSlices.y.repaint.call(loadNrrdSlices.y);
  loadNrrdSlices.z.repaint.call(loadNrrdSlices.z);

  displayAndCalculateNSR();
  
  (tumourSliceIndex as ICommXYZ).x = loadNrrdSlices.x.index;
  (tumourSliceIndex as ICommXYZ).y = loadNrrdSlices.y.index;
  (tumourSliceIndex as ICommXYZ).z = loadNrrdSlices.z.index;

  requestUpdateSliderSettings();
  });
  
}

function displayAndCalculateNSR(){
  console.log("displayAndCalculateNSR");
  console.log(tumourPosition);
  
  
  if (!!tumourPosition) {
      // const nippleTree = createKDTree(nipplesPos);
      // const idx = nippleTree.nn([tumourCenter.x,tumourCenter.y,tumourCenter.z])
      // console.log(idx);
      if(!!ribTree && !!skinTree){
        displaySkinAndRib([tumourPosition.x, tumourPosition.y, tumourPosition.z])
      }
      updateTumourPanelInfo(tumourPosition)
    }
}



function displaySkinAndRib(tumourPosition:number[]){

  const skinidx = skinTree.nn(tumourPosition)
  const ribidx = ribTree.nn(tumourPosition)

  skinSphere.position.set(processedSkinPoints[skinidx][0],processedSkinPoints[skinidx][1], processedSkinPoints[skinidx][2])
  ribSphere.position.set(processedRibPoints[ribidx][0],processedRibPoints[ribidx][1], processedRibPoints[ribidx][2])
  skinPosition.set(processedSkinPoints[skinidx][0],processedSkinPoints[skinidx][1], processedSkinPoints[skinidx][2])
  ribPosition.set(processedRibPoints[ribidx][0],processedRibPoints[ribidx][1], processedRibPoints[ribidx][2])

  copperScene.scene.add( skinSphere, ribSphere)

  allRightPanelMeshes.push(skinSphere)
  allRightPanelMeshes.push(ribSphere)
}

/**
* Update nipple skin and ribcage to tumour center distance 
* @param tumourPosition 
*/
function updateTumourPanelInfo(tumourPosition: THREE.Vector3){
  const nippleLeft = new THREE.Vector3(
      nippleTl[0],
      nippleTl[1],
      nippleTl[2]
    );
    const nippleRight = new THREE.Vector3(
      nippleTr[0],
      nippleTr[1],
      nippleTr[2]
    );
    const clockInfo = getClosestNipple(nippleLeft, nippleRight, tumourPosition);

    nippleDist.value = clockInfo.dist;
    // console.log(clockInfo.radial_distance, nippleCentralLimit);

    if (clockInfo.radial_distance < nippleCentralLimit) {
      nippleClock.value = "central";
    } else {
      nippleClock.value = "@ " + clockInfo.timeStr;
    }

    if(!!ribTree && !!skinTree){
      skinDist.value = tumourPosition.distanceTo(skinPosition).toFixed(0)
      ribDist.value = tumourPosition.distanceTo(ribPosition).toFixed(0)
    }
}


const handleViewSigleClick = (view: string) => {
  panelOperator.start();
  copperScene.controls.mouseButtons.LEFT = -1;
  clickCount++;
  if (clickCount === 1) {
    clickTimer = setTimeout(() => {
      switch (view) {
        case "sagittal":
          loadNrrdMeshes.x.visible = true;
          loadNrrdMeshes.y.visible = false;
          loadNrrdMeshes.z.visible = false;
          panelOperator.setSlicePrams(loadNrrdSlices.x);
          break;
        case "axial":
          loadNrrdMeshes.x.visible = false;
          loadNrrdMeshes.y.visible = false;
          loadNrrdMeshes.z.visible = true;
          panelOperator.setSlicePrams(loadNrrdSlices.z);
          break;
        case "coronal":
          loadNrrdMeshes.x.visible = false;
          loadNrrdMeshes.y.visible = true;
          loadNrrdMeshes.z.visible = false;
          panelOperator.setSlicePrams(loadNrrdSlices.y);
          break;
        case "clock":
          validFlag = !validFlag;
          // valideClock(
          //   validFlag,
          //   copperScene,
          //   baseContainer.value as HTMLElement,
          //   nippleTl,
          //   nippleTr,
          //   loadNrrdMeshes
          // );
          break;
        case "3dview":
          backTo3DView()
          break;
        case "reset":
          resetNrrdImage();
          break;
        
      }
      clickCount = 0;
    }, 200);
  }
};

const handleViewsDoubleClick = (view: string) => {

  if(view == "reset" || view == "3dview") return;
  
  !!clickTimer && clearTimeout(clickTimer);
  clickCount = 0;
  copperScene.controls.mouseButtons.LEFT = -1;
  copperScene.controls.reset();
  switch (view) {
    case "sagittal":
      loadNrrdMeshes.x.visible = true;
      loadNrrdMeshes.y.visible = false;
      loadNrrdMeshes.z.visible = false;
      panelOperator.setSlicePrams(loadNrrdSlices.x);
      copperScene.loadViewUrl("/nrrd_view_sagittal.json");
      break;

    case "axial":
      loadNrrdMeshes.x.visible = false;
      loadNrrdMeshes.y.visible = false;
      loadNrrdMeshes.z.visible = true;
      panelOperator.setSlicePrams(loadNrrdSlices.z);
      copperScene.loadViewUrl("/nrrd_view.json");
      break;

    case "coronal":
      loadNrrdMeshes.x.visible = false;
      loadNrrdMeshes.y.visible = true;
      loadNrrdMeshes.z.visible = false;
      panelOperator.setSlicePrams(loadNrrdSlices.y);
      copperScene.loadViewUrl("/nrrd_view_coronal.json");
      break;
  }
};


function removeOldMeshes(meshSet: THREE.Object3D[]) {
  if (!!copperScene) {
    (copperScene as Copper.copperScene).scene.remove(...meshSet);
    meshSet.forEach((element) => {
      element.traverse((case_mesh) => {
        if ((case_mesh as THREE.Mesh).isMesh) {
          (case_mesh as THREE.Mesh).geometry.dispose();
        }
      });
    });
    meshSet.length = 0;
  }
} 

const resetSliceIndex = (sliceIndex: ICommXYZ) => {
  if(sliceIndex.x === 0 && sliceIndex.y === 0 && sliceIndex.z ===0 )return;

  loadNrrdMeshes.x.renderOrder = 1;
  loadNrrdMeshes.y.renderOrder = 1;
  loadNrrdMeshes.z.renderOrder = 1;
  loadNrrdSlices.x.index = sliceIndex.x;
  loadNrrdSlices.y.index = sliceIndex.y;
  loadNrrdSlices.z.index = sliceIndex.z;
  loadNrrdSlices.x.repaint.call(loadNrrdSlices.x);
  loadNrrdSlices.y.repaint.call(loadNrrdSlices.y);
  loadNrrdSlices.z.repaint.call(loadNrrdSlices.z);
  
    // request to mount/update slider settings
  requestUpdateSliderSettings()
};


const backTo3DView = ()=>{
  panelOperator.dispose();
  
  loadNrrdMeshes.x.visible = true;
  loadNrrdMeshes.y.visible = true;
  loadNrrdMeshes.z.visible = true;
  // valideClock(false, copperScene, baseContainer.value as HTMLElement);
  
  copperScene.controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
}

const resetNrrdImage = () => {
  copperScene.loadViewUrl("/nrrd_view.json");
  copperScene.controls.reset();
  backTo3DView();
  resetSliceIndex(tumourSliceIndex);
};

onUnmounted(() => {
  emitter.off("Common:ResizeCopperSceneWhenNavChanged", emitterOnResizeCopperSceneWhenNavChanged);
  emitter.off("Segmentation:CaseDetails", emitterOnCaseDetails);
  emitter.off("Segmentation:SyncTumourModelButtonClicked", emitterOnSyncTumourModelButtonClicked);
  emitter.off("Segmentation:RegisterButtonStatusChanged", emitterOnRegisterButtonStatusChanged);
  emitter.off("SegmentationTrial:DrawSphereFunction", emitterOnDrawSphereFunction)
  emitter.off("Common:ToggleBreastVisibility", emitterOnToggleBreastVisibility)
});
</script>

<style scoped>

</style>
