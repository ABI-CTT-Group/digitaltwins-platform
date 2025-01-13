<template>

  <div id="bg" ref="base_container" class="dark guide-left-panel" @keydown="(event)=>setUpMouseWheel(event,'down')" @keyup="(event)=>setUpMouseWheel(event,'up')">
    <div ref="canvas_container" class="canvas_container"></div>
    <!-- <div ref="slice_index_container" class="copper3d_sliceNumber">
      Tumour Segmentation Panel
    </div> -->

    <v-card class="left-value-panel mt-2">
      <div class="dtn"><span>DTN:</span> <span>{{ dtn }} mm</span></div>
      <div class="dts"><span>DTS:</span> <span>{{ dts }} mm</span></div>
      <div class="dtr"><span>DTR:</span> <span>{{ dtr }} mm</span></div>
    </v-card>
  </div>
  <div
    class="nav_bar_left_calculation_container"
    ref="nav_bar_left_container"
  >
    <NavBar
      :file-num="fileNum"
      :max="max"
      :immediate-slice-num="immediateSliceNum"
      :contrast-index="contrastNum"
      :init-slice-index="initSliceIndex"
      @on-slice-change="getSliceChangedNum"
      @on-change-orientation="resetSlicesOrientation"
    ></NavBar>
  </div>
</template>
<script setup lang="ts">
import { GUI, GUIController } from "dat.gui";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
// import * as Copper from "@/ts/index";
import loadingGif from "@/assets/loading.svg";

import NavBar from "@/components/commonBar/NavBarCalculation.vue";
import { onMounted, ref, watchEffect, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import {
  ITumourStudyAppDetails,
  ITumourStudyReport,
  ITumourStudyAppDetail,
  ILoadedMeshes,
} from "@/models/apiTypes";
import { addNameToLoadedMeshes, getIncompleteCases } from "@/plugins/view-utils/utils-left";
import {useTumourStudyDetailsStore, useTumourStudyNrrdStore } from "@/store/tumour_position_study_app";
import {useSaveTumourStudyReport} from "@/plugins/tumour_position_study_api";

import {
  getEraserUrlsForOffLine,
  getCursorUrlsForOffLine,
} from "@/plugins/view-utils/tools";
// import emitter from "@/plugins/custom-emitter";;
import emitter from "@/plugins/custom-emitter";


let appRenderer: Copper.copperRenderer;
let max = ref(0);
let immediateSliceNum = ref(0);
let contrastNum = ref(0);
let fileNum = ref(0);
let initSliceIndex = ref(0);

let base_container = ref<HTMLDivElement>();
let canvas_container = ref<HTMLDivElement>();
let nav_bar_left_container = ref<HTMLDivElement>();
// let slice_index_container = ref<HTMLDivElement>();

let scene: Copper.copperScene | undefined;
let pre_slices = ref();

let gui = new GUI({ width: 300, autoPlace: false });
let nrrdTools: Copper.NrrdTools;
let loadBarMain: Copper.loadingBarType;
let loadingContainer: HTMLDivElement, progress: HTMLDivElement;
let allSlices: Array<any> = [];
let defaultRegAllSlices: Array<any> = [];
let allLoadedMeshes: Array<ILoadedMeshes> = [];
let defaultRegAllMeshes: Array<ILoadedMeshes> = [];

let currentContrastUrls: Array<string> = [];

let filesCount = ref(0);
let firstLoad = true;



let dts = ref(0);
let dtn = ref(0);
let dtr = ref(0);

let toolsState: any;

const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const { studyNrrd } = storeToRefs(useTumourStudyNrrdStore());
const { getStudyNrrd } = useTumourStudyNrrdStore();


const incompleteCases = ref<ITumourStudyAppDetail[]>([]);
const workingCase = ref<ITumourStudyAppDetail | null>(null);

const eraserUrls = getEraserUrlsForOffLine();
const cursorUrls = getCursorUrlsForOffLine();

let coreRenderId = 0;


function manageEmitters() {
  emitter.on("TumourStudy:NextCase", emitterOnNextCase);
  emitter.on("TumourStudy:CaseReport", emitterOnCaseReport);
}

const emitterOnNextCase = ()=>{
  //update incomplete cases
  incompleteCases.value = getIncompleteCases(studyDetails.value!.details);
  if (incompleteCases.value.length > 0) {
    workingCase.value = incompleteCases.value[0];
    onCaseSwitched()
  }else{
    emitter.emit("TumourStudy:AllCasesCompleted");
  }
}
const emitterOnCaseReport = async (report:ITumourStudyReport)=>{
  // update study details
  workingCase.value!.report = report;
  workingCase.value!.report.complete = true;

  // save report to backend
  await useSaveTumourStudyReport(Object.assign({case_name:workingCase.value!.name}, workingCase.value!.report));
}

onMounted(async () => {
  manageEmitters();

  appRenderer = new Copper.copperRenderer(
    base_container.value as HTMLDivElement,
    {
      guiOpen: false,
      alpha: true,
    }
  );

  nrrdTools = new Copper.NrrdTools(canvas_container.value as HTMLDivElement);
  // nrrdTools.setDisplaySliceIndexPanel(
  //   slice_index_container.value as HTMLDivElement
  // );
  // for offline working
  nrrdTools.setEraserUrls(eraserUrls);
  nrrdTools.setPencilIconUrls(cursorUrls);

  nrrdTools.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Slice";

  // setNrrdTools(nrrdTools);

  // sphere plan b
  toolsState = nrrdTools.getNrrdToolsSettings();

  loadBarMain = Copper.loading(loadingGif);

  loadingContainer = loadBarMain.loadingContainer;

  progress = loadBarMain.progress;

  (canvas_container.value as HTMLDivElement).appendChild(
    loadBarMain.loadingContainer
  );

  setupCopperScene("nrrd_tools");
  appRenderer.animate();

  await getInitData();
});

function setUpMouseWheel(e:KeyboardEvent, status: "down" | "up") {
  if(status === "down"){
    nrrdTools.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Zoom";
    nrrdTools.updateMouseWheelEvent();
  }else if(status === "up"){
    nrrdTools.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Slice";
    nrrdTools.updateMouseWheelEvent();
  }
}
 

async function getInitData() {
  if(!!studyDetails.value === false) await getTumourStudyDetails();
  if (studyDetails.value?.details) {
    incompleteCases.value = getIncompleteCases(studyDetails.value?.details);

    // get first incomplete case nrrd image
    if (incompleteCases.value.length > 0) {
      workingCase.value = incompleteCases.value[0];
      onCaseSwitched()
    }
  }
}


const resetSlicesOrientation = (axis: "x" | "y" | "z") => {
  nrrdTools.setSliceOrientation(axis);
  max.value = nrrdTools.getMaxSliceNum()[1];
  const { currentIndex, contrastIndex } =
    nrrdTools.getCurrentSlicesNumAndContrastNum();
  immediateSliceNum.value = currentIndex;
  contrastNum.value = contrastIndex;
};
const getSliceChangedNum = (sliceNum: number) => {
  nrrdTools.setSliceMoving(sliceNum);
};

const switchAnimationStatus = (status: "flex" | "none", text?: string) => {

  loadingContainer.style.display = status;
  !!text && (progress.innerText = text);
};


function distance3D(x1:number, y1:number, z1:number, x2:number, y2:number, z2:number) {
    let dx = x2 - x1;
    let dy = y2 - y1;
    let dz = z2 - z1;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

const getCalculateSpherePositionsData = (tumourSphereOrigin:Copper.ICommXYZ | null, skinSphereOrigin:Copper.ICommXYZ | null, ribSphereOrigin:Copper.ICommXYZ | null, nippleSphereOrigin:Copper.ICommXYZ | null, aix:"x"|"y"|"z")=>{
  console.log("tumourOrigin: ",tumourSphereOrigin);
  
   if(tumourSphereOrigin === null) return;

   if (skinSphereOrigin !== null){
     dts.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], skinSphereOrigin[aix][0], skinSphereOrigin[aix][1], skinSphereOrigin[aix][2]).toFixed(2));
      // send to calculator component: status (skin, nipple, ribcage), position, distance 
     emitter.emit("TumourStudy:Status", nrrdTools.gui_states.cal_distance, skinSphereOrigin.z, dts.value);
   }
   if (ribSphereOrigin !== null){
     dtr.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], ribSphereOrigin[aix][0], ribSphereOrigin[aix][1], ribSphereOrigin[aix][2]).toFixed(2));
     emitter.emit("TumourStudy:Status", nrrdTools.gui_states.cal_distance, ribSphereOrigin.z, dtr.value);
   }
   if (nippleSphereOrigin !== null){
     dtn.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], nippleSphereOrigin[aix][0], nippleSphereOrigin[aix][1], nippleSphereOrigin[aix][2]).toFixed(2));
     emitter.emit("TumourStudy:Status", nrrdTools.gui_states.cal_distance, nippleSphereOrigin.z, dtn.value);
   } 
}


watchEffect(() => {
  if (
    filesCount.value != 0 &&
    allSlices.length != 0 &&
    filesCount.value === currentContrastUrls.length
  ) {
    console.log("All files ready!");
    allSlices.sort((a: any, b: any) => {
      return a.order - b.order;
    });
    allLoadedMeshes.sort((a: any, b: any) => {
      return a.order - b.order;
    });

    nrrdTools.clear();
    nrrdTools.setAllSlices(allSlices);

    defaultRegAllSlices = [...allSlices];
    defaultRegAllMeshes = [...allLoadedMeshes];

    initSliceIndex.value = nrrdTools.getCurrentSliceIndex();

    const getSliceNum = (index: number, contrastindex: number) => {
      immediateSliceNum.value = index;
      contrastNum.value = contrastindex;
    };

    if (firstLoad) {
      nrrdTools.drag({
        getSliceNum,
      });
      nrrdTools.draw({ getCalculateSpherePositionsData });
      nrrdTools.setupGUI(gui);
      coreRenderId = scene?.addPreRenderCallbackFunction(nrrdTools.start) as number;
      // xyz: 84 179 74
      emitter.emit("TumourStudy:NrrdTools", nrrdTools);
    } else {
      nrrdTools.redrawMianPreOnDisplayCanvas();
    }

    max.value = nrrdTools.getMaxSliceNum()[1];
    setTimeout(() => {
      initSliceIndex.value = 0;
      filesCount.value = 0;
      // const guiSettings = nrrdTools.getGuiSettings();
    }, 1000);
    emitter.emit("TumourStudy:ImageLoaded", workingCase.value);
    firstLoad = false;
    switchAnimationStatus("none");
}});

async function setupCopperScene(name: string) {
  scene = appRenderer.getSceneByName(name) as Copper.copperScene;
  if (scene == undefined) {
    scene = appRenderer.createScene(name) as Copper.copperScene;
    if (scene) {
      appRenderer.setCurrentScene(scene);
    }
  }
}

// request case nrrd image from backend, and get the nrrd image blob url
async function onCaseSwitched() {
  if (currentContrastUrls.length > 0) {
    currentContrastUrls.forEach((url) => URL.revokeObjectURL(url));
    currentContrastUrls = [];
  }
  switchAnimationStatus("flex", "loading image data, please wait......");
  await getStudyNrrd(workingCase.value?.file_path as string);
  currentContrastUrls.push(studyNrrd.value as string);
  // revoke the regsiter images
  readyToLoad("registration");
}

const readyToLoad = (name: string) => {
  fileNum.value = currentContrastUrls.length;
  if (currentContrastUrls.length > 0) {
    return new Promise<{ meshes: Array<Copper.nrrdMeshesType>; slices: any[] }>(
      (resolve, reject) => {
        loadCurrentCase(currentContrastUrls, name, resolve, reject);
      }
    );
  }
};

const loadCurrentCase = (
  urls: Array<string>,
  name: string,
  resolve?: (value: {
    meshes: Array<Copper.nrrdMeshesType>;
    slices: any[];
  }) => void,
  reject?: (reason?: any) => void
) => {
  switchAnimationStatus("none");
  fileNum.value = urls.length;

  allSlices = [];
  allLoadedMeshes = [];
  const mainPreArea = (
    volume: any,
    nrrdMesh: Copper.nrrdMeshesType,
    nrrdSlices: Copper.nrrdSliceType
    // gui?: GUI
  ) => {
    addNameToLoadedMeshes(nrrdMesh, name);
    const newNrrdSlice = Object.assign(nrrdSlices, { order: 0 });
    const newNrrdMesh = Object.assign(nrrdMesh, { order: 0 });
    allSlices.push(newNrrdSlice);
    allLoadedMeshes.push(newNrrdMesh);
    pre_slices.value = nrrdSlices;
    filesCount.value += 1;
  };
  scene?.loadNrrd(urls[0], loadBarMain, true, mainPreArea);

  for (let i = 1; i < urls.length; i++) {
    scene?.loadNrrd(
      urls[i],
      loadBarMain,
      true,
      (
        volume: any,
        nrrdMesh: Copper.nrrdMeshesType,
        nrrdSlices: Copper.nrrdSliceType
      ) => {
 
        addNameToLoadedMeshes(nrrdMesh, name);
        const newNrrdSlice = Object.assign(nrrdSlices, { order: i });
        const newNrrdMesh = Object.assign(nrrdMesh, { order: i });
        allSlices.push(newNrrdSlice);
        allLoadedMeshes.push(newNrrdMesh);
        filesCount.value += 1;
        if (filesCount.value >= urls.length) {
          allLoadedMeshes.sort((a: any, b: any) => {
            return a.order - b.order;
          });
          allSlices.sort((a: any, b: any) => {
            return a.order - b.order;
          });
          !!resolve && resolve({ meshes: allLoadedMeshes, slices: allSlices });
        }
      }
    );
  }
};

onUnmounted(() => {
  emitter.off("TumourStudy:NextCase", emitterOnNextCase);
  emitter.off("TumourStudy:CaseReport", emitterOnCaseReport);
  scene?.removePreRenderCallbackFunction(coreRenderId);
});

</script>

<style>
#bg {
  width: 100%;
  /* height: 100vh; */
  flex: 0 0 90%;
  overflow: hidden;
  position: relative;
  /* border: 1px solid palevioletred; */
}

.left_gui {
  /* position: fixed; */
  position: absolute;
  top: 0;
  right: 0;
  z-index: 100;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
.canvas_container {
  /* position: fixed; */
  position: absolute;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.nav_bar_left_calculation_container {
  flex: 1;
  display: flex;
  position: absolute;
  align-items: center;
  justify-content: center;
  width: 100%;
  bottom: 5%;
}

.copper3d_sliceNumber {
  position: absolute;
  width: 300px;
  text-align: center;
  top: 5% !important;
  right: 1% !important;
  left: 0px !important;
  margin: 0 auto;
  border: 3px solid salmon;
  border-radius: 10px;
  padding: 5px;
  font-size: 0.9em;
  font-weight: 700;
  color: rgba(26, 26, 26, 0.965);
  cursor: no-drop;
  transition: border-color 0.25s;
}

.copper3d_sliceNumber:hover {
  border-color: #eb4a05;
}
.copper3d_sliceNumber:focus,
.copper3d_sliceNumber:focus-visible {
  outline: 4px auto -webkit-focus-ring-color;
}

.dark .copper3d_sliceNumber {
  border: 3px solid #009688;
  color: #fff8ec;
}

.dark .copper3d_sliceNumber:hover {
  border-color: #4db6ac;
}

.copper3D_scene_div {
  display: flex;
  justify-content: center;
  align-items: center;
}

.copper3D_loading_progress {
  color: darkgray !important;
  text-align: center;
  width: 60%;
}
.copper3D_drawingCanvasContainer {
  max-width: 80%;
  max-height: 80%;
}

.left-value-panel {
  position: absolute !important;
  z-index: 10000;
  left: 15px;
  top: 0px;
  width: 200px;
  height: 80px;
  background-color: rgba(255, 255, 255, 0.1) !important;
  border: 2px solid rgba(255, 255, 255, 0.3) !important;
  border-radius: 10px !important;
  padding: 10px 15px !important;
  font-size: smaller !important;
  user-select: text !important;
  -webkit-user-select: text !important;
  /* display: flex; */
  /* align-items: center; */
  /* justify-content: center; */
}

.left-value-panel > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.left-value-panel .dts {
  color: #FFEB3B;
}
.left-value-panel .dtr {
  color: darkcyan;
}
.left-value-panel .dtn {
  color: hotpink;
}
</style>
