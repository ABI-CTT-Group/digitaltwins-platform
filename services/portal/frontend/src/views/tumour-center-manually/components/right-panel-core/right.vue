<template>
  <div id="right_panel" ref="right_panel" class="guide-right-panel">
    <div v-show="openLoading" ref="loading_container" class="loading">
      <div class="loading_text text-cyan-darken-3">Load tumour model...</div>
    </div>
    <v-card class="right-value-panel mt-2 guide-right-value-panel" color="right-display-panel">
      <div color="primary">
        <span>Tumour volume:</span> <span>{{ tumourVolume }} cm<sup>3</sup></span>
      </div>
      <div><span>Tumour extent:</span> <span>{{ tumourExtent }} mm</span></div>
      <div class="skin"><span>Skin:</span> <span>{{ skinDist }} mm</span></div>
      <div class="ribcage"><span>Ribcage:</span> <span>{{ ribDist }} mm</span></div>
      <div class="nipple">
        <span>Nipple:</span> <span>{{ nippleDist }} mm</span>
      </div>
      <div class="nipple">
        <span></span> <span>{{ nippleClock }}</span>
      </div>
    </v-card>
    <div></div>
    <div ref="right_panel_gui" class="right_gui"></div>
  </div>
  <div v-show="panelWidth >= 410 ? true : false" class="nav_bar_right_container" ref="nav_bar_right_container">

      <NavBarRight
        :panel-width="Math.ceil(panelWidth) "
        @on-view-single-click="handleViewSigleClick"
        @on-view-double-click="handleViewsDoubleClick"
      />

  </div>
</template>

<script setup lang="ts">
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
  reactive,
  toRefs,
} from "vue";
import Drawer from "@/components/commonBar/drawer.vue";
import NavBarRight from "@/components/commonBar/NavBarRight.vue";
import emitter from "@/plugins/custom-emitter";;
import { storeToRefs } from "pinia";
import {
  useMaskNrrdStore,
  useMaskMeshObjStore,
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
  ISaveSphere,
} from "@/models/apiTypes";
import {
  findCurrentCase,
  transformMeshPointToImageSpace,
  getClosestNipple,
  createOriginSphere
} from "@/plugins/view-utils/tools";
import { PanelOperationManager, valideClock, deepClone, processPointsCloud } from "./utils-right";
import loadingGif from "@/assets/loading.svg";

type Props = {
  panelWidth: number;
};

let right_panel = ref<HTMLDivElement>();
let appRenderer: Copper.copperRenderer;
let panelOperator: PanelOperationManager;
let right_panel_gui = ref<HTMLDivElement>();
let loading_container = ref<HTMLDivElement>();
let loadBar1: Copper.loadingBarType;
let casename: string;

let copperScene: Copper.copperScene;
let socket = new WebSocket("ws://127.0.0.1:8000/ws");
let socketTimer: NodeJS.Timer;

let loadBarMain: Copper.loadingBarType;
let loadingContainer: HTMLDivElement;

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
const { maskMeshObj } = storeToRefs(useMaskMeshObjStore());
const { getMaskMeshObj } = useMaskMeshObjStore();
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
const { panelWidth } = toRefs(reactive(props));


watch(panelWidth, (newVal, oldVal) => {
  copperScene?.onWindowResize();
});


// App entry

onMounted(() => {
  manageEmitters();

  loadBarMain = Copper.loading(loadingGif);

  loadingContainer = loadBarMain.loadingContainer;
  (loading_container.value as HTMLDivElement).appendChild(loadingContainer);

  

  appRenderer = new Copper.copperRenderer(right_panel.value as HTMLDivElement, {
    guiOpen: false,
    alpha: true,
    logarithmicDepthBuffer: true,
  });

  appRenderer.renderer.domElement.style.position = "fixed"
  // appRenderer.renderer.sortObjects = false;
  panelOperator = new PanelOperationManager(right_panel.value as HTMLDivElement);

  loadBar1 = Copper.loading(loadingGif);

  // appRenderer.container.appendChild(loadBar1.loadingContainer);

  initScene("display_nrrd");

  initSocket()

  appRenderer.animate();
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
      if(!!maskMeshObj.value.maskMeshObjUrl){
        console.log("remove old mesh");
        
        URL.revokeObjectURL(maskMeshObj.value.maskMeshObjUrl)
      }
      const blob = new Blob([event.data], { type: "model/obj" });
      const url = URL.createObjectURL(blob);
      if(!!maskMeshObj.value.maskMeshObjUrl) maskMeshObj.value.maskMeshObjUrl = url;

      if(!!preTumourShpere){
        (copperScene as Copper.copperScene).scene.remove(preTumourShpere);
        preTumourShpere = undefined;
      }
      
      loadSegmentTumour(url)
      loadingContainer.style.display = "none";
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

function requestSocketUpdateTumourModel() {
  const intervalId = setInterval(() => {
    socket.send("Frontend socket connect!");
  }, 1000);
  return intervalId;
}

function initScene(name: string) {
  copperScene = appRenderer.getSceneByName(name) as Copper.copperScene;
  if (copperScene == undefined) {
    copperScene = appRenderer.createScene(name) as Copper.copperScene;
    appRenderer.setCurrentScene(copperScene);

    // config controls
    const controls = copperScene.controls as Copper.Copper3dTrackballControls;
    // controls.noPan = true;
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.ROTATE,
      RIGHT: THREE.MOUSE.PAN,
    };

    controls.rotateSpeed = 3.5;
    controls.panSpeed = 0.5;

    //update camera views
    copperScene.loadViewUrl("/nrrd_view.json");

    // Config threejs environment background
    // copperScene.updateBackground("#8b6d96", "#18e5e5");
    // Copper.setHDRFilePath("venice_sunset_1k.hdr");
    // appRenderer.updateEnvironment();
  }
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
}


function manageEmitters() {
  /**
   * UI Control layer
   * */ 
  // emitter.on("containerHight", (h) => {
  //   (right_panel.value as HTMLDivElement).style.height = `${h}vh`;
  // });
  emitter.on("Common:ResizeCopperSceneWhenNavChanged", () => {
    // give a 300ms delay for wait right panel to recalculate width, then update threejs
    setTimeout(() => {
      copperScene?.onWindowResize();
    }, 300);
  });

  /**
   * Logic layer
   * */ 

  // switch cases
  emitter.on("Segmentation:CaseDetails", async (case_details: ICaseDetails) => {
    // 1. clear previous meshes and clear state
    clearModelsAndStates()
    // 2. request data
    const case_infos: ICaseDetails = case_details;
    const case_detail = findCurrentCase(
      case_infos.details,
      case_infos.currentCaseId
    );


    // 2.1 Get casename and the nrrd image URL blob
    casename = case_infos.currentCaseId;
    maskNrrd.value = case_infos.maskNrrd;
    console.log("maskNrrd", maskNrrd.value);
    
    // 2.2 Load Nrrd

    loadNrrd(maskNrrd.value as string, "register")?.then(async (nrrdData)=>{
      await getSkinPoints(case_infos.currentCaseId);
      await getRibPoints(case_infos.currentCaseId);
      await getBreastMeshObj(case_infos.currentCaseId);
      
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

      if(!!maskMeshObj.value.maskMeshObjUrl){
        URL.revokeObjectURL(maskMeshObj.value.maskMeshObjUrl)
      }
      await getMaskMeshObj(casename);
      
      if(!!maskMeshObj.value){
        tumourVolume.value = Math.ceil(maskMeshObj.value.meshVolume as number) / 1000;
        // maskMeshObj.value.maskMeshObjUrl as string
        
        // 2.4 load tumour model
        loadSegmentTumour(maskMeshObj.value.maskMeshObjUrl as string)
      }else{
        requestUpdateSliderSettings();
      }
   
    });

    
  });

  // switch segmented tumour mesh 3D obj model
  emitter.on("Segmentation:SyncTumourModelButtonClicked", () => {
    loadingContainer.style.display = "flex";
    openLoading.value = true;
    socketTimer = requestSocketUpdateTumourModel();
  });

  // Listen to switch register images and origin images
  emitter.on("Segmentation:RegisterButtonStatusChanged", (data: ILeftRightData) => {
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
        loadBar1,
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
        },
        {
          openGui: false,
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
  });

  
  // When left panel draw sphere, then the right panel need automatically update the sphere tumour
  emitter.on("SegmentationTrial:DrawSphereFunction",(val: ISaveSphere)=>{

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
  })

  emitter.on("Common:ToggleBreastVisibility", (val:boolean)=>{
   
    if (!!breast3DModel){
      breast3DModel.traverse((child)=>{
        if((child as THREE.Mesh).isMesh){
          child.visible = val;
        }
      })
    }
  })
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
    // container: right_panel_gui.value,
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
    loadBar1,
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
  await getNipplePoints(casename);
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
          //   right_panel.value as HTMLElement,
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
  // valideClock(false, copperScene, right_panel.value as HTMLElement);
  
  copperScene.controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
}

const resetNrrdImage = () => {
  copperScene.loadViewUrl("/nrrd_view.json");
  copperScene.controls.reset();
  backTo3DView();
  resetSliceIndex(tumourSliceIndex);
};

</script>

<style scoped>
#right_panel {
  width: 95%;
  flex: 0 0 90%;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  /* overflow: hidden;
  position: relative; */
}

.right_gui {
  position: absolute;
  top: 0;
  right: 0;
}

.nav_bar_right_container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.loading {
  /* position: fixed; */
  position: absolute;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.loading_text {
  order: 3;
}
.right-value-panel {
  position: absolute;
  left: 0px;
  top: 0px;
  width: 200px;
  height: 150px;
  background-color: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 10px;
  padding: 10px 15px;
  font-size: smaller;
  user-select: none;
  -webkit-user-select: none;
  /* display: flex; */
  /* align-items: center; */
  /* justify-content: center; */
}

.right-value-panel > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skin {
  color: #FFEB3B;
}
.ribcage {
  color: darkcyan;
}
.nipple {
  color: hotpink;
}

.btn {
  position: absolute;
  bottom: 10px;
  right: 20px;
}
button {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100px;
  border-radius: 2px;
  border: 1px solid transparent;
  padding: 0.6em 1.2em;
  font-size: 1em;
  font-weight: 500;
  font-family: inherit;

  background-color: #f9f9f9;
  cursor: pointer;
  transition: border-color 0.25s;
  z-index: 999;
}
button:hover {
  border-color: #646cff;
  background-color: rgba(0, 0, 0, 0.1);
}
button:focus,
button:focus-visible {
  outline: 4px auto -webkit-focus-ring-color;
}
</style>
