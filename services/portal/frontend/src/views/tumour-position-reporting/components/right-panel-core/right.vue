<template>
  <RightPanelCore
    ref="rightPanelCoreRef"
    :show-bottom-nav-bar="panelWidth >= 410 ? true : false"
    :show-loading-animation="openLoading"
    @update:finished-copper-init="onFinishedCopperInit"
    @update:reset-nrrd-image-view="handleResetNrrdImageView"
  >
    <template #tumour-distance-panel>
      <TumourDistancePanelRight 
        :show-volume="false"
        :show-extent="false"
        :skin-dist="skinDist"
        :rib-dist="ribDist"
        :nipple-dist="nippleDist"
        :nipple-clock="nippleClock"
      />
    </template>
    <template #bottom-nav-bar>
      <NavBarRight
        :panel-width="Math.ceil(panelWidth) "
        :settings="sliderSettingsValue"
        @on-view-single-click="handleViewSingleClick"
        @on-view-double-click="handleViewsDoubleClick"
      />
    </template>
  </RightPanelCore>
</template>

<script setup lang="ts">
import RightPanelCore from "@/components/view-components/RightPanelCore.vue";
import NavBarRight from "@/components/commonBar/NavBarRight.vue";
import TumourDistancePanelRight from "@/components/view-components/TumourDistancePanelRight.vue";
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
  useMaskTumourObjDataStore,
  useBreastMeshObjUrlStore,
  useNipplePointsStore,
  useRibPointsStore,
  useSkinPointsStore
} from "@/store/app";
import {
  ICommXYZ,
  ILeftRightData,
  INipplePoints,
  IRibSkinPoints,
  ITumourCenterCaseDetails
} from "@/models/apiTypes";
import {
  transformMeshPointToImageSpace,
  getClosestNipple
} from "@/plugins/view-utils/tools";
import { PanelOperationManager, valideClock, deepClone, processPointsCloud } from "@/plugins/view-utils/utils-right";
import { switchAnimationStatus } from "@/components/view-components/leftCoreUtils";


/**
 * Notice: 3D Nrrd render as pixel not mm.
 * formulas for converting mm and pixel via image spacing
 * pixel / spacing = mm
 * mm * spacing = pixel
 * 
 * Duke university provides, tumour center and bounding box are using mm, 
 * so when we render in threejs we need to convert mm to pixel and add the image origin + threejs world center bias.
 * 
 * The tumour, nipple, ribcage, and skin positions that we save to backend are mm, so when save we need to convert the pixel position to mm.
 */

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
let sliderSettingsValue = ref<{
    panelOperator: PanelOperationManager;
    dimensions: number[];
    spacing: number[];
    currentValue: number[];
}>();


let currentCasename = ref<string>("");
let currentImageType = ref<"register"|"origin">("register");

// Right panel display state
const openLoading = ref(false);


let allRightPanelMeshes: Array<THREE.Object3D> = [];
let loadNrrdMeshes: Copper.nrrdMeshesType;
let loadNrrdSlices: Copper.nrrdSliceType;


// the nrrd origin + bais for display tumour, breast model, skin, ribcage, nipple
let correctedOrigin = [0,0,0];
let nrrdOrigin:number[] = []
let nrrdSpacing:number[] = [];
let nrrdRas:number[] = []; // mm
let nrrdDimensions:number[] = []; // pixels
let nrrdBias:THREE.Vector3 = new THREE.Vector3(0,0,0);

let segementTumour3DModel:THREE.Group|THREE.Mesh|undefined = undefined;
let breast3DModel:THREE.Group|undefined;
let registrationMeshes: Copper.nrrdMeshesType | undefined;
let originMeshes: Copper.nrrdMeshesType | undefined;
let registrationSlices: Copper.nrrdSliceType | undefined;
let originSlices: Copper.nrrdSliceType | undefined;


let tumourSliceIndex: ICommXYZ = {x:0, y:0, z:0};
// tumour center position in mm
let tumourCenterMM:ICommXYZ;
// tumour center position in pixel
let tumourCenterPixel:ICommXYZ;
let boxWidtHeightDepthMM:ICommXYZ;
let boxWidtHeightDepthPixel:ICommXYZ;
// tumour position in threejs world space in pixel + threejs world center bias
let tumourPosition:THREE.Vector3|undefined = undefined;
const Geometry = new THREE.SphereGeometry(3, 32, 16)
const tumourMaterial = new THREE.MeshBasicMaterial({ color: "#228b22" });
const tumourSphere = new THREE.Mesh(Geometry, tumourMaterial);

let nippleCentralLimit = 10;
let nippleTl: number[] = [];
let nippleTr: number[] = [];
let skinTree:any;
let ribTree:any;
let processedSkinPoints:number[][] = []
let processedRibPoints:number[][] = []
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



const maskNrrd = ref<string>("");
const { breastMeshObjUrl } = storeToRefs(useBreastMeshObjUrlStore());
const { getBreastMeshObjUrl } = useBreastMeshObjUrlStore();
const skinDist = ref("0");
const ribDist = ref("0");
const nippleDist = ref("L: 0");
const nippleClock = ref("@ 0:0");
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

});



function onFinishedCopperInit(data: { appRenderer: Copper.copperRenderer, copperScene: Copper.copperScene, panelOperator: PanelOperationManager }) {
  copperScene = data.copperScene;
  panelOperator = data.panelOperator;

}

function clearModelsAndStates(){
  // when switch case, we need to clear previous models and states
  registrationMeshes = undefined;
  originMeshes = undefined;
  registrationSlices = undefined;
  originSlices = undefined;
  segementTumour3DModel = undefined;
  breast3DModel = undefined;
  tumourSliceIndex = {x:0, y:0, z:0};
  tumourPosition = undefined;
  correctedOrigin = [0,0,0];
  nrrdOrigin.length = 0
  nrrdSpacing.length = 0
  nrrdRas.length = 0
  nrrdDimensions.length = 0
  nrrdBias = new THREE.Vector3(0,0,0);
  !!skinTree?skinTree.dispose():null;
  !!ribTree?ribTree.dispose():null;
  skinTree = undefined;
  ribTree = undefined;
  rightPanelCoreRef.value?.removeOldMeshes(allRightPanelMeshes);
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
  // Once the tumour position is changed from left panel, we need to update the right panel
  emitter.on("TumourStudy:UpdateTumourPosition", emitterOnUpdateTumourPosition);
}

const emitterOnCaseDetails = async (caseDetails: ITumourCenterCaseDetails) => {
  // 1. clear previous meshes and clear state
  clearModelsAndStates()
  // 2.1 Get currentCasename and get the init data
  await getInitDataOnceCaseSwitched(caseDetails);

  currentImageType.value = "register"

  // 2.2 Load Nrrd core
  coreLoadNrrdImageOnceGetCaseDetail(maskNrrd.value as string, currentImageType.value);
}
const emitterOnResizeCopperSceneWhenNavChanged = () => {
  // give a 300ms delay for wait right panel to recalculate width, then update threejs
  setTimeout(() => {
    copperScene?.onWindowResize();
  }, 300);
}

const emitterOnUpdateTumourPosition = (tumourSphereOrigin: ICommXYZ) => {
  // Note: the tumour center now we set to (pixel, pixel, mm) in Axial view, in threejs world we need to convert it to (pixel, pixel, pixel) and add the image origin + threejs world center bias.
  // pixel / spacing = mm
  // mm * spacing = pixel
  if (!nrrdSpacing || nrrdSpacing.length === 0) return;
  // add the image origin in threejs world center bias
  const tumourCenterPixel = {
    x: correctedOrigin[0] + tumourSphereOrigin.x,
    y: correctedOrigin[1] + tumourSphereOrigin.y,
    z: correctedOrigin[2] + tumourSphereOrigin.z * nrrdSpacing[2]
  }
  loadTumourViaPositionCenter(tumourCenterPixel);
}

const convertMMPointToPixelPoint = (point:ICommXYZ, spacing:number[]):ICommXYZ => {
  return {
    x: point.x * spacing[0],
    y: point.y * spacing[1],
    z: point.z * spacing[2]
  };
}

const updateNrrdMeshToCopperScene = (updatedNrrdMesh:Copper.nrrdMeshesType, updatedNrrdSlice:Copper.nrrdSliceType, recordSliceIndex?:any) => {
  if (!!loadNrrdMeshes) copperScene.scene.remove(...[loadNrrdMeshes.x, loadNrrdMeshes.y, loadNrrdMeshes.z]);
  loadNrrdMeshes = updatedNrrdMesh;
  loadNrrdSlices = updatedNrrdSlice;
  if (!!recordSliceIndex) resetSliceIndex(recordSliceIndex);
  copperScene.scene.add(...[loadNrrdMeshes.x, loadNrrdMeshes.y, loadNrrdMeshes.z]);
};

const getInitDataOnceCaseSwitched = async (caseDetails: ITumourCenterCaseDetails)=>{
  
  currentCasename.value = caseDetails.currentCaseName;

  // get mask nrrd blob url
  maskNrrd.value = caseDetails.nrrdUrl;
  
  tumourCenterMM = caseDetails.tumourWindow!.center;
  const maxPoint = caseDetails.tumourWindow!.bounding_box_max_point;
  const minPoint = caseDetails.tumourWindow!.bounding_box_min_point;
  boxWidtHeightDepthMM = {
    x: maxPoint.x - minPoint.x,
    y: maxPoint.y - minPoint.y,
    z: maxPoint.z - minPoint.z
  };
  // get breast mesh obj url
  await getBreastMeshObjUrl(currentCasename.value);
  // get ribcage points
  await getRibPoints(currentCasename.value);
  // get skin points
  await getSkinPoints(currentCasename.value);
  // get nipple points
  await getNipplePoints(currentCasename.value);
}


const coreLoadNrrdImageOnceGetCaseDetail = async (nrrdUrl:string, imageType:"origin"|"register") => {
  rightPanelCoreRef.value
    ?.loadNrrd(nrrdUrl, imageType)
    ?.then(async (nrrdData)=>{

      nrrdOrigin = nrrdData.origin;
      nrrdSpacing = nrrdData.spacing;
      nrrdRas = nrrdData.ras;
      nrrdDimensions = nrrdData.dimensions;
      nrrdBias = new THREE.Vector3(nrrdData.bias.x, nrrdData.bias.y, nrrdData.bias.z);
      correctedOrigin = nrrdData.correctedOrigin;
      const { nrrdMesh, nrrdSlices } = nrrdData;
      
      if(currentImageType.value==="register"){
        loadNrrdMeshes = registrationMeshes = nrrdMesh;
        loadNrrdSlices = registrationSlices = nrrdSlices;
      }else{
        loadNrrdMeshes = originMeshes = nrrdMesh;
        loadNrrdSlices = originSlices = nrrdSlices;
      }

      const sliceIndex: ICommXYZ  = {
        x: loadNrrdSlices.x.RSAMaxIndex / 2,
        y: loadNrrdSlices.y.RSAMaxIndex / 2,
        z: loadNrrdSlices.z.RSAMaxIndex / 2,  
      }

      updateNrrdMeshToCopperScene(nrrdMesh, nrrdSlices, sliceIndex);
      allRightPanelMeshes.push(nrrdMesh.x, nrrdMesh.y, nrrdMesh.z);
      // reset view
      rightPanelCoreRef.value?.resetNrrdImageView(loadNrrdMeshes);


      // Note: the tomour center you get here is from the backend, it's in mm, so we need to convert it to pixel
      tumourCenterPixel = convertMMPointToPixelPoint(tumourCenterMM, nrrdSpacing);
      boxWidtHeightDepthPixel = convertMMPointToPixelPoint(boxWidtHeightDepthMM, nrrdSpacing);
      // Note: the tumour center now we set to (pixel, pixel, mm) in Axial view, in threejs world we need to convert it to (pixel, pixel, pixel) and add the image origin + threejs world center bias.
      const correctedTumourCenterPosition = {
        x: correctedOrigin[0]+tumourCenterPixel.x,
        y: correctedOrigin[1]+tumourCenterPixel.y, 
        z: correctedOrigin[2]+tumourCenterPixel.z
      }

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
      loadBreastNipplePoints(nipplePoints.value as INipplePoints);
      // 2.4 Load tumour center point
      loadTumourViaPositionCenter(correctedTumourCenterPosition)
      // 2.5 Load tumour bounding box
      // loadTumourBoundingBox(correctedTumourCenterPosition, boxWidtHeightDepthPixel);
  
      loadBreastModel(breastMeshObjUrl.value as string);
      // 2.6 Load tumour obj model if has
      requestUpdateSliderSettings();
    });
};

function loadBreastNipplePoints(nipplePoints:INipplePoints){
  if(!!nipplePoints){
    const nipples = nipplePoints;
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

    allRightPanelMeshes.push(...[nippleSphereL, nippleSphereR]);
  }
}

const loadTumourBoundingBox = (center:ICommXYZ, boxWidtHeightDepth:ICommXYZ) => {
  // bunding box
  const geometry = new THREE.BoxGeometry( boxWidtHeightDepth.x, boxWidtHeightDepth.y, boxWidtHeightDepth.z ); 
  const material = new THREE.MeshBasicMaterial( {color: 0x00ff00} ); 
  const cube = new THREE.Mesh( geometry, material ); 

  cube.position.set(center.x, center.y, center.z);
  const box = new THREE.BoxHelper( cube, 0xffffff );
  copperScene.addObject( box );
  allRightPanelMeshes.push(box);
}

const loadTumourViaPositionCenter = (center:ICommXYZ)=>{
  // Note: The center here must be under (pixel, pixel, pixel) format + threejs world center bias for nrrd image
  if(!center) return;

  tumourSphere.position.set(center.x, center.y, center.z);
  if (!tumourPosition) {
    tumourPosition = new THREE.Vector3()
  }
  tumourPosition?.set(center.x, center.y, center.z);

  loadNrrdSlices.x.index = (tumourSliceIndex as ICommXYZ).x =
  loadNrrdSlices.x.RSAMaxIndex / 2 + tumourSphere.position.x;
  loadNrrdSlices.y.index = (tumourSliceIndex as ICommXYZ).y =
  loadNrrdSlices.y.RSAMaxIndex / 2 + tumourSphere.position.y;
  loadNrrdSlices.z.index = (tumourSliceIndex as ICommXYZ).z =
  loadNrrdSlices.z.RSAMaxIndex / 2 + tumourSphere.position.z;
  loadNrrdSlices.x.repaint.call(loadNrrdSlices.x);
  loadNrrdSlices.y.repaint.call(loadNrrdSlices.y);
  loadNrrdSlices.z.repaint.call(loadNrrdSlices.z);
  copperScene.scene.add(tumourSphere);
  allRightPanelMeshes.push(tumourSphere);

  updateSkinAndRibcageThenCalculateDTNSR()
}

async function loadBreastModel(url:string){ 
  // load breast model
  if (!url) return;
  copperScene.loadOBJ(url, (content) => {
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

const updateSkinAndRibcageThenCalculateDTNSR = ()=>{
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

const handleViewSingleClick = (view: string) => {
  rightPanelCoreRef.value?.onNavBarSingleClick(view, loadNrrdMeshes, loadNrrdSlices);
};

const handleViewsDoubleClick = (view: string) => {
  rightPanelCoreRef.value?.onNavBarDoubleClick(view, loadNrrdMeshes, loadNrrdSlices);
};

function requestUpdateSliderSettings(){
  // update settings, and automatically send to nav bar
  sliderSettingsValue.value = {
        panelOperator,
        dimensions:nrrdDimensions,
        spacing: nrrdSpacing, 
        currentValue:[
          Math.ceil(loadNrrdSlices.x.index / nrrdSpacing[0]),
          Math.ceil(loadNrrdSlices.y.index / nrrdSpacing[1]),
          Math.ceil(loadNrrdSlices.z.index / nrrdSpacing[2])
        ]
      };
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

const handleResetNrrdImageView = () => {
  resetSliceIndex(tumourSliceIndex);
};

onUnmounted(() => {
  emitter.off("Common:ResizeCopperSceneWhenNavChanged", emitterOnResizeCopperSceneWhenNavChanged);
  emitter.off("Segmentation:CaseDetails", emitterOnCaseDetails);
});
</script>

<style scoped>

</style>
