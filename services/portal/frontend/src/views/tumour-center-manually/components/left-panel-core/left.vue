<template>

  <!-- <div id="bg" ref="base_container" class="dark guide-left-panel" @keydown="(event)=>setUpMouseWheel(event,'down')" @keyup="(event)=>setUpMouseWheel(event,'up')">-->
  <LeftPanelCore
    ref="leftPanelCoreRef"
    :show-debug-panel="false" 
    :show-slice-index="true"
    :enable-upload="false"
    :show-tumour-distance-panel="true"
    :show-bottom-nav-bar="panelWidth >= 800 ? true : false"
    :current-case-contrast-urls="currentCaseContrastUrls"
    :current-case-name="currentCaseName"
    :emitter="emitter"
    @update:finished-copper-init="onFinishedCopperInit"
    @update:calculate-sphere-positions-data="getCalculateSpherePositionsData"
    @update:slice-number="getSliceNum"
    @update:after-load-all-case-images="handleAllImagesLoaded"
  >
    <template #bottom-nav-bar>
      <NavBar
        :file-num="currentCaseContractsCount"
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
import LeftPanelCore from "@/components/view-components/LeftPanelCore.vue";
import NavBar from "@/components/commonBar/NavBarCalculation.vue";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
import { onMounted, ref, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import {
  ITumourStudyAppDetails,
  ITumourStudyReport,
  ITumourStudyAppDetail,
  ILoadedMeshes,
  ILeftCoreCopperInit,
  IToolCalculateSpherePositionsData,
  IToolGetSliceNumber,
  IToolAfterLoadImagesResponse
} from "@/models/apiTypes";
import { getTumourCenterInCompleteCases, distance3D, customRound } from "@/plugins/view-utils/utils-left";
import {useTumourStudyDetailsStore, useTumourStudyNrrdStore, } from "@/store/tumour_position_study_app";
import {useSaveTumourStudyReport} from "@/plugins/tumour_position_study_api";
import { switchAnimationStatus } from "@/components/view-components/leftCoreUtils";
import { useSaveTumourPosition } from "@/plugins/api";

import emitter from "@/plugins/custom-emitter";


type Props = {
  panelWidth?: number;
};

withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

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
let currentCaseContractsCount = ref(0);
let initSliceIndex = ref(0);


let displaySlices: Array<any> = [];
let displayLoadedMeshes: Array<ILoadedMeshes> = [];


let currentCaseContrastUrls = ref<Array<string>>([]);
let currentCaseName = ref("");


const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const { studyNrrd } = storeToRefs(useTumourStudyNrrdStore());
const { getStudyNrrd } = useTumourStudyNrrdStore();


const incompleteCases = ref<ITumourStudyAppDetail[]>([]);
const workingCase = ref<ITumourStudyAppDetail | null>(null);



function manageEmitters() {
  emitter.on("TumourStudy:NextCase", emitterOnNextCase);
  emitter.on("TumourStudy:CaseReport", emitterOnCaseReport);
  emitter.emit("Common:OnAppMounted", "TumourStudy:Admin-TumourCenter");
}

const emitterOnNextCase = ()=>{
  //update incomplete cases
  incompleteCases.value = getTumourCenterInCompleteCases(studyDetails.value!.details);
  if (incompleteCases.value.length > 0) {
    workingCase.value = incompleteCases.value[0];
    onCaseSwitched()
  }else{
    emitter.emit("TumourStudy:AllCasesCompleted");
  }
}
const emitterOnCaseReport = async (report:ITumourStudyReport)=>{
  // update study details
  // save report to backend

  workingCase.value!.tumour_window.validate = true;
  await useSaveTumourPosition({
    case_name: currentCaseName.value, 
    position: workingCase.value!.tumour_window.center, 
    validate: workingCase.value!.tumour_window.validate});
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
    incompleteCases.value = getTumourCenterInCompleteCases(studyDetails.value?.details);

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

/**
 * The Skin, Ribcage, Nipple, and Tumour Points that we get from the Copper3D is using this format:
 * {
 *  x: pixel,
 *  y: pixel,
 *  z: mm
 * }
 * @param res 
 */
const getCalculateSpherePositionsData = async (res:IToolCalculateSpherePositionsData)=>{
  // Note: the tumour center now we set to (pixel, pixel, mm) in Axial view, in calculate distance we need to convert it to (mm, mm, mm)
  // pixel / spacing = mm
  // mm * spacing = pixel
  const { tumourSphereOrigin, skinSphereOrigin, ribSphereOrigin, nippleSphereOrigin, aix } = res;
   if(tumourSphereOrigin === null){
    return;
   }else{
      emitter.emit("TumourStudy:UpdateTumourPosition", {
        x: tumourSphereOrigin.z[0],
        y: tumourSphereOrigin.z[1],
        z: tumourSphereOrigin.z[2],
      })
      const spacing = nrrdTools?.nrrd_states.voxelSpacing!;
      const toumourCenterMM = {
        x: tumourSphereOrigin.z[0] / spacing[0],
        y: tumourSphereOrigin.z[1] / spacing[1],
        z: tumourSphereOrigin.z[2]
      }
      workingCase.value!.tumour_window.center = toumourCenterMM;
   }
}
const getSliceNum = (res: IToolGetSliceNumber) => {
  const { index, contrastindex } = res;
  immediateSliceNum.value = index;
  contrastNum.value = contrastindex;
};

const handleAllImagesLoaded = async (res:IToolAfterLoadImagesResponse) => {
  // step 1: get all images and meshes and store them in displaySlices and displayLoadedMeshes
  displaySlices = res.allSlices;
  displayLoadedMeshes = res.allLoadedMeshes;
  // step 2: config nav bar slider
  initSliceIndex.value = nrrdTools!.getCurrentSliceIndex();
  max.value = nrrdTools!.getMaxSliceNum()[1];
  // step 3: tell all relevant components that all images are loaded
  emitter.emit("TumourStudy:ImageLoaded", workingCase.value);
}

// request case nrrd image from backend, and get the nrrd image blob url
async function onCaseSwitched() {
  if (currentCaseContrastUrls.value.length > 0) {
    currentCaseContrastUrls.value.forEach((url) => URL.revokeObjectURL(url));
    currentCaseContrastUrls.value = [];
  }
  switchAnimationStatus(loadingContainer!, progress!, "flex", "loading image data, please wait......");
  await getStudyNrrd(workingCase.value?.file_path as string);

  //Note: Important must use a new array to trigger the watcher, cannot use push
  currentCaseContrastUrls.value = [studyNrrd.value as string];
  currentCaseName.value = workingCase.value?.name as string;

  emitter.emit("Segmentation:CaseDetails", {
    currentCaseName: currentCaseName.value,
    tumourWindow: workingCase.value?.tumour_window,
    nrrdUrl:  studyNrrd.value
  });
  currentCaseContractsCount.value = currentCaseContrastUrls.value.length;
}

onUnmounted(() => {
  emitter.off("TumourStudy:NextCase", emitterOnNextCase);
  emitter.off("TumourStudy:CaseReport", emitterOnCaseReport);
});

</script>

<style>
</style>
