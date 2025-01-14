<template>

  <!-- <div id="bg" ref="base_container" class="dark guide-left-panel" @keydown="(event)=>setUpMouseWheel(event,'down')" @keyup="(event)=>setUpMouseWheel(event,'up')">-->
  <LeftPanelCore
    ref="leftPanelCoreRef"
    :show-debug-panel="false" 
    :show-slice-index="true"
    :enable-upload="false"
    :show-tumour-distance-panel="true"
    :show-bottom-nav-bar="true"
    @finished-copper-init="onFinishedCopperInit"
  >
    <template #tumour-distance-panel>
      <TumourDistancePanelLeft :dts="dts" :dtn="dtn" :dtr="dtr" />
    </template>
    <template #bottom-nav-bar>
      <NavBar
        :file-num="fileNum"
        :max="max"
        :immediate-slice-num="immediateSliceNum"
        :contrast-index="contrastNum"
        :init-slice-index="initSliceIndex"
        @on-slice-change="getSliceChangedNum"
        @on-change-orientation="resetSlicesOrientation"
      ></NavBar>
    </template>
  </LeftPanelCore>
</template>
<script setup lang="ts">
import TumourDistancePanelLeft from "@/components/view-components/TumourDistancePanelLeft.vue";
import LeftPanelCore from "@/components/view-components/LeftPanelCore.vue";
import NavBar from "@/components/commonBar/NavBarCalculation.vue";

import { GUI, GUIController } from "dat.gui";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
// import * as Copper from "@/ts/index";

import { onMounted, ref, watchEffect, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import {
  ITumourStudyAppDetails,
  ITumourStudyReport,
  ITumourStudyAppDetail,
  ILoadedMeshes,
  ILeftCoreCopperInit
} from "@/models/apiTypes";
import { addNameToLoadedMeshes, getIncompleteCases } from "@/plugins/view-utils/utils-left";
import {useTumourStudyDetailsStore, useTumourStudyNrrdStore } from "@/store/tumour_position_study_app";
import {useSaveTumourStudyReport} from "@/plugins/tumour_position_study_api";

import emitter from "@/plugins/custom-emitter";


const leftPanelCoreRef = ref<InstanceType<typeof LeftPanelCore>>();

let nrrdTools: Copper.NrrdTools | undefined;
let scene: Copper.copperScene | undefined;
let loadBarMain: Copper.loadingBarType | undefined;
let loadingContainer: HTMLDivElement | undefined;
let progress: HTMLDivElement | undefined;
let gui:any;
let baseContainer: HTMLDivElement | undefined;

let max = ref(0);
let immediateSliceNum = ref(0);
let contrastNum = ref(0);
let fileNum = ref(0);
let initSliceIndex = ref(0);


let allSlices: Array<any> = [];
let defaultRegAllSlices: Array<any> = [];
let allLoadedMeshes: Array<ILoadedMeshes> = [];
let defaultRegAllMeshes: Array<ILoadedMeshes> = [];

let currentCaseContrastUrls: Array<string> = [];

let filesCount = ref(0);
let firstLoad = true;



let dts = ref(0);
let dtn = ref(0);
let dtr = ref(0);


const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const { studyNrrd } = storeToRefs(useTumourStudyNrrdStore());
const { getStudyNrrd } = useTumourStudyNrrdStore();


const incompleteCases = ref<ITumourStudyAppDetail[]>([]);
const workingCase = ref<ITumourStudyAppDetail | null>(null);

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
  loadBarMain = leftPanelCoreRef.value?.loadBarMain;
  loadingContainer = leftPanelCoreRef.value?.loadingContainer;
  progress = leftPanelCoreRef.value?.progress;
  gui = leftPanelCoreRef.value?.gui;
  baseContainer = leftPanelCoreRef.value?.baseContainer;

  manageEmitters();
  await getInitData();
});

const onFinishedCopperInit = async (copperInitData: ILeftCoreCopperInit) => {
  nrrdTools = copperInitData.nrrdTools;
  scene = copperInitData.scene;
  nrrdTools!.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Slice";
};

function setUpMouseWheel(e:KeyboardEvent, status: "down" | "up") {
  console.log("setUpMouseWheel", e.key, status);
  
  if(status === "down"){
    nrrdTools!.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Zoom";
    nrrdTools!.updateMouseWheelEvent();
  }else if(status === "up"){
    nrrdTools!.nrrd_states.keyboardSettings.mouseWheel = "Scroll:Slice";
    nrrdTools!.updateMouseWheelEvent();
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
  nrrdTools!.setSliceOrientation(axis);
  max.value = nrrdTools!.getMaxSliceNum()[1];
  const { currentIndex, contrastIndex } =
    nrrdTools!.getCurrentSlicesNumAndContrastNum();
  immediateSliceNum.value = currentIndex;
  contrastNum.value = contrastIndex;
};
const getSliceChangedNum = (sliceNum: number) => {
  nrrdTools!.setSliceMoving(sliceNum);
};

const switchAnimationStatus = (status: "flex" | "none", text?: string) => {

  console.log(loadingContainer);
  
  loadingContainer!.style.display = status;
  !!text && (progress!.innerText = text);
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
     emitter.emit("TumourStudy:Status", nrrdTools!.gui_states.cal_distance, skinSphereOrigin.z, dts.value);
   }
   if (ribSphereOrigin !== null){
     dtr.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], ribSphereOrigin[aix][0], ribSphereOrigin[aix][1], ribSphereOrigin[aix][2]).toFixed(2));
     emitter.emit("TumourStudy:Status", nrrdTools!.gui_states.cal_distance, ribSphereOrigin.z, dtr.value);
   }
   if (nippleSphereOrigin !== null){
     dtn.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], nippleSphereOrigin[aix][0], nippleSphereOrigin[aix][1], nippleSphereOrigin[aix][2]).toFixed(2));
     emitter.emit("TumourStudy:Status", nrrdTools!.gui_states.cal_distance, nippleSphereOrigin.z, dtn.value);
   } 
}


watchEffect(() => {
  if (
    filesCount.value != 0 &&
    allSlices.length != 0 &&
    filesCount.value === currentCaseContrastUrls.length
  ) {
    console.log("All files ready!");
    allSlices.sort((a: any, b: any) => {
      return a.order - b.order;
    });
    allLoadedMeshes.sort((a: any, b: any) => {
      return a.order - b.order;
    });

    nrrdTools!.clear();
    nrrdTools!.setAllSlices(allSlices);

    defaultRegAllSlices = [...allSlices];
    defaultRegAllMeshes = [...allLoadedMeshes];

    initSliceIndex.value = nrrdTools!.getCurrentSliceIndex();

    const getSliceNum = (index: number, contrastindex: number) => {
      immediateSliceNum.value = index;
      contrastNum.value = contrastindex;
    };

    if (firstLoad) {
      nrrdTools!.drag({
        getSliceNum,
      });
      nrrdTools!.draw({ getCalculateSpherePositionsData });
      nrrdTools!.setupGUI(gui);
      coreRenderId = scene?.addPreRenderCallbackFunction(nrrdTools!.start) as number;
      // xyz: 84 179 74
      emitter.emit("Core:NrrdTools", nrrdTools);
    } else {
      nrrdTools!.redrawMianPreOnDisplayCanvas();
    }

    max.value = nrrdTools!.getMaxSliceNum()[1];
    setTimeout(() => {
      initSliceIndex.value = 0;
      filesCount.value = 0;
      // const guiSettings = nrrdTools!.getGuiSettings();
    }, 1000);
    emitter.emit("TumourStudy:ImageLoaded", workingCase.value);
    firstLoad = false;
    switchAnimationStatus("none");
}});


// request case nrrd image from backend, and get the nrrd image blob url
async function onCaseSwitched() {
  if (currentCaseContrastUrls.length > 0) {
    currentCaseContrastUrls.forEach((url) => URL.revokeObjectURL(url));
    currentCaseContrastUrls = [];
  }
  switchAnimationStatus("flex", "loading image data, please wait......");
  await getStudyNrrd(workingCase.value?.file_path as string);
  currentCaseContrastUrls.push(studyNrrd.value as string);
  // revoke the regsiter images
  readyToLoad("registration");
}

const readyToLoad = (name: string) => {
  fileNum.value = currentCaseContrastUrls.length;
  if (currentCaseContrastUrls.length > 0) {
    return new Promise<{ meshes: Array<Copper.nrrdMeshesType>; slices: any[] }>(
      (resolve, reject) => {
        loadCurrentCase(currentCaseContrastUrls, name, resolve, reject);
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
    filesCount.value += 1;
  };
  scene?.loadNrrd(urls[0], loadBarMain as Copper.loadingBarType, true, mainPreArea);

  for (let i = 1; i < urls.length; i++) {
    scene?.loadNrrd(
      urls[i],
      loadBarMain as Copper.loadingBarType,
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
</style>
