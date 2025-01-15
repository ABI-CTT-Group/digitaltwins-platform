<template>
  <LeftPanelCore 
    ref="leftPanelCoreRef"
    v-model:load-mask="loadMask"
    :show-debug-panel="isShowDebugPanel" 
    :show-slice-index="true"
    :enable-upload="true"
    :show-tumour-distance-panel="showCalculatorValue"
    :show-bottom-nav-bar="panelWidth >= 600 ? true : false"
    :current-case-contrast-urls="currentCaseContrastUrls"
    :current-case-name="currentCaseName"
    @finished-copper-init="onFinishedCopperInit"
    @update:get-mask-data="getMaskData"
    @update:set-mask-data="setMaskData"
    @update:sphere-data="getSphereData"
    @update:calculate-sphere-positions-data="getCalculateSpherePositionsData"
    @update:slice-number="getSliceNum"
    @update:mouse-drag-contrast="getContrastMove"
    @update:after-load-all-case-images="handleAllImagesLoaded"
    >
    <template #drag-to-upload>
      <Upload
        :dialog="dialog"
        @on-close-dialog="onCloseDialog"
        @get-load-files-urls="handleUploadFiles"
      />
    </template>
    <template #tumour-distance-panel>
      <TumourDistancePanel :dts="dts" :dtn="dtn" :dtr="dtr" />
    </template>
    <template #bottom-nav-bar>
      <NavBar
        :file-num="currentCaseContractsCount"
        :max="max"
        :immediate-slice-num="immediateSliceNum"
        :contrast-index="contrastNum"
        :init-slice-index="initSliceIndex"
        @on-slice-change="getSliceChangedNum"
        @reset-main-area-size="resetMainAreaSize"
        @on-change-orientation="resetSlicesOrientation"
        @on-save="onSaveMask"
        @on-open-dialog="onOpenDialog"
      />
    </template>
  </LeftPanelCore>
</template>
<script setup lang="ts">
import LeftPanelCore from "@/components/view-components/LeftPanelCore.vue";
import TumourDistancePanel from "@/components/view-components/TumourDistancePanelLeft.vue";
import NavBar from "@/components/commonBar/NavBar.vue";
import Upload from "@/components/commonBar/Upload.vue";

import { GUI, GUIController } from "dat.gui";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
// import * as Copper from "@/ts/index";

import { onMounted, ref, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import {
  IStoredMasks,
  IReplaceMask,
  ISaveSphere,
  ILoadUrls,
  IRegRquest,
  ILoadedMeshes,
  ICaseUrls,
  IDetails,
  ILeftCoreCopperInit,
  IToolMaskData,
  IToolSphereData,
  IToolCalculateSpherePositionsData,
  IToolAfterLoadImagesResponse,
  IToolGetSliceNumber,
  IToolGetMouseDragContrastMove
} from "@/models/apiTypes";
import { findRequestUrls, customRound, distance3D } from "@/plugins/view-utils/utils-left";
import {
  useSegmentationCasesStore,
  useInitMarksStore,
  useReplaceMarksStore,
  useSaveSphereStore,
  useSaveMasksStore,
  useMaskStore,
  useClearMaskMeshStore,
  useNrrdCaseFileUrlsWithOrderStore,
} from "@/store/app";
import { useSaveTumourPosition } from "@/plugins/api";
import {
  findCurrentCase,
  revokeAppUrls,
  revokeCaseUrls,
} from "@/plugins/view-utils/tools";
import emitter from "@/plugins/custom-emitter";
import { convertInitMaskData } from "@/plugins/worker";
import { switchAnimationStatus } from "@/components/view-components/leftCoreUtils";


type Props = {
  panelWidth: number;
};
type TContrastSelected = {
  [key: string]: boolean;
};

withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

const leftPanelCoreRef = ref<InstanceType<typeof LeftPanelCore>>();
// to tell left core component to load mask data or not
let loadMask = ref(true);
// to tell left core component to show debug panel or not
let isShowDebugPanel = ref(false);
// core current case urls, used to trigger left core to load images in watch hook
let currentCaseContrastUrls = ref<Array<string>>([]);
// record the current case name
let currentCaseName = ref("");

let nrrdTools: Copper.NrrdTools | undefined;
let scene: Copper.copperScene | undefined;
let loadBarMain: Copper.loadingBarType | undefined;
let loadingContainer: HTMLDivElement | undefined;
let progress: HTMLDivElement | undefined;
let gui:any;
let baseContainer: HTMLDivElement | undefined;

// nav bar slider config
let max = ref(0);
let immediateSliceNum = ref(0);
let contrastNum = ref(0);
let currentCaseContractsCount = ref(0);
let initSliceIndex = ref(0);

// upload dialog config
let dialog = ref(false);

// core image data
let displaySlices: Array<any> = [];
let displayLoadedMeshes: Array<ILoadedMeshes> = [];
let registerSlices: Array<any> = [];
let regitserMeshes: Array<ILoadedMeshes> = [];
let originSlices: Array<any> = [];
let originMeshes: Array<ILoadedMeshes> = [];
let originUrls: ICaseUrls = { nrrdUrls: [], jsonUrl: "" };
let regiterUrls: ICaseUrls = { nrrdUrls: [], jsonUrl: "" };
let loadedUrls: ILoadUrls = {};

// Gui settings
let regCkeckbox: GUIController;
let selectedContrastFolder: GUI;
let regCheckboxElement: HTMLInputElement;
let optsGui: GUI | undefined = undefined;
let state = {
  showContrast: false,
  switchCase: "",
  showRegisterImages: true,
  release: () => {
    revokeAppUrls(loadedUrls);
    loadedUrls = {};
  },
};

// true means current we load register images
// false means current we load origin images
let regiterSwitchBarStatus = true;

// tumour distance calculation panel data
let dts = ref(0);
let dtn = ref(0);
let dtr = ref(0);

const showCalculatorValue = ref(false);


const { allCasesDetails } = storeToRefs(useSegmentationCasesStore());
const { getAllCasesDetails } = useSegmentationCasesStore();
const { sendInitMask } = useInitMarksStore();
const { sendReplaceMask } = useReplaceMarksStore();
const { sendSaveSphere } = useSaveSphereStore();
const { sendSaveMask } = useSaveMasksStore();
const { maskBackend } = storeToRefs(useMaskStore());
const { getMaskDataBackend } = useMaskStore();
const { clearMaskMeshObj } = useClearMaskMeshStore();
const { getNrrdAndJsonFileUrls } = useNrrdCaseFileUrlsWithOrderStore();
const { caseUrls } = storeToRefs(useNrrdCaseFileUrlsWithOrderStore());

onMounted(async () => {
  loadBarMain = leftPanelCoreRef.value?.loadBarMain;
  loadingContainer = leftPanelCoreRef.value?.loadingContainer;
  progress = leftPanelCoreRef.value?.progress;
  gui = leftPanelCoreRef.value?.gui;
  baseContainer = leftPanelCoreRef.value?.baseContainer;

  // get init data
  await getInitData();
  
  manageEmitters();
  setupGui();
});

async function getInitData() {
  await getAllCasesDetails();
}

const onFinishedCopperInit = (copperInitData:ILeftCoreCopperInit)=>{
  nrrdTools = copperInitData.nrrdTools;
  scene = copperInitData.scene;
}

function manageEmitters() {
  emitter.on("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox)
  emitter.on("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox)
  emitter.on("Common:DebugMode", emitterOnDebugMode);
  emitter.on("Common:ToggleAppTheme", emitterOnToggleAppTheme);
  emitter.on("Segementation:CaseSwitched", emitterOnCaseSwitched);
  emitter.on("Segmentation:ContrastChanged", emitterOnContrastChanged);
  emitter.on("Segmentation:RegisterImageChanged", emitteOnRegisterImageChanged);
}

const emitterOnOpenCalculatorBox =  ()=>{
    showCalculatorValue.value = true
};
const emitterOnCloseCalculatorBox = ()=>{
    showCalculatorValue.value = false
};
const emitterOnDebugMode = (flag: boolean) => {
  isShowDebugPanel.value = flag;
};
const emitterOnToggleAppTheme = () => {
    baseContainer!.classList.toggle("dark");
};
const emitterOnCaseSwitched = async (casename: string) => {
  await onCaseSwitched(casename);
};
const emitterOnContrastChanged = (result: any) => {
  const { contrastState, order } = result;
  onContrastSelected(contrastState, order);
};
const emitteOnRegisterImageChanged = async (result: boolean) => {
    await onRegistedStateChanged(result);
};

// nav bar hook functions
const onSaveMask = async (flag: boolean) => {
  if (flag && nrrdTools!.protectedData.maskData.paintImages.z.length > 0) {
    switchAnimationStatus(loadingContainer!, progress!, "flex", "Saving masks data, please wait......");
    await sendSaveMask(currentCaseName.value);
    switchAnimationStatus(loadingContainer!, progress!, "none");
    emitter.emit("Segmentation:SyncTumourModelButtonClicked", true);
  }
};

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
const resetMainAreaSize = (factor: number) => {
  nrrdTools!.setMainAreaSize(factor);
};

// upload dialog hook functions
const onOpenDialog = (flag: boolean) => {
  dialog.value = flag;
};
const onCloseDialog = (flag: boolean) => {
  dialog.value = flag;
};
const handleUploadFiles = (urls: string[]) =>{
  currentCaseContrastUrls.value = urls;
}

// left core hook functions
const sendInitMaskToBackend = async () => {
  // const masksData = nrrdTools!.paintImages.z;
  const rawMaskData = nrrdTools!.getMaskData();
  const masksData = {
    label1: rawMaskData.paintImagesLabel1.z,
    label2: rawMaskData.paintImagesLabel2.z,
    label3: rawMaskData.paintImagesLabel3.z,
  };
  const dimensions = nrrdTools!.getCurrentImageDimension();
  const len = rawMaskData.paintImages.z.length;
  const width = dimensions[0];
  const height = dimensions[1];
  const voxelSpacing = nrrdTools!.getVoxelSpacing();
  const spaceOrigin = nrrdTools!.getSpaceOrigin();
  
  
  if (len > 0) {
    const result = convertInitMaskData({
      masksData,
      len,
      width,
      height,
      voxelSpacing,
      spaceOrigin,
      msg: "init",
    });
    const body = {
      caseId: currentCaseName.value,
      masks: result.masks as IStoredMasks,
    };
    let start_c: unknown = new Date();
    await sendInitMask(body);
    let end_c: unknown = new Date();
    let timeDiff_c = (end_c as number) - (start_c as number);
    console.log(`axios send Time taken: ${timeDiff_c}ms`);
    console.log("send");
  }
};

const loadJsonMasks = (url: string) => {
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Loading masks data......");

  const xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.responseType = "json";
  xhr.onload = function () {
    if (xhr.status === 200) {
      const data = xhr.response;
      if (data === null) {
        console.log("data empty init");
        sendInitMaskToBackend();
      }
      nrrdTools!.setMasksData(data, loadBarMain);
    }
  };
  xhr.send();
};

const setMaskData = () => {
  if (loadedUrls[currentCaseName.value]) {
    if (allCasesDetails.value) {
      const currentCaseDetail = findCurrentCase(
        allCasesDetails.value.details,
        currentCaseName.value
      );

      if (currentCaseDetail.masked) {
        if (caseUrls.value)
          loadJsonMasks(loadedUrls[currentCaseName.value].jsonUrl as string);
      } else {
        sendInitMaskToBackend();
      }
    }
  }
  setTimeout(() => {
    // wait for loading mask, give a delay before user start operate
    switchAnimationStatus(loadingContainer!, progress!, "none");
  }, 1000);
};

const getSphereData = async (res: IToolSphereData) => {
  const { sphereOrigin, sphereRadius } = res;
  const sphereData: ISaveSphere = {
    caseId: currentCaseName.value,
    sliceId: sphereOrigin[2],
    origin: nrrdTools!.nrrd_states.spaceOrigin,
    spacing: nrrdTools!.nrrd_states.voxelSpacing,
    sphereRadiusMM: sphereRadius,
    sphereOriginMM: [sphereOrigin[0],sphereOrigin[1],sphereOrigin[2]*nrrdTools!.nrrd_states.voxelSpacing[2]],
  };

  emitter.emit("SegmentationTrial:DrawSphereFunction", sphereData);

  await sendSaveSphere(sphereData);
};

const getCalculateSpherePositionsData = async (res:IToolCalculateSpherePositionsData)=>{

  const { tumourSphereOrigin, skinSphereOrigin, ribSphereOrigin, nippleSphereOrigin, aix } = res;
    // Note: the tumour center now we set to (pixel, pixel, mm) in Axial view, in calculate distance we need to convert it to (mm, mm, mm)
    // pixel / spacing = mm
    // mm * spacing = pixel
   if(tumourSphereOrigin === null){
     return;
   }else{
    const position = {
      x: customRound(tumourSphereOrigin["z"][0]/nrrdTools!.nrrd_states.voxelSpacing[0]),
      y: customRound(tumourSphereOrigin["z"][1]/nrrdTools!.nrrd_states.voxelSpacing[1]),
      z: customRound(tumourSphereOrigin["z"][2]),
    }
    await useSaveTumourPosition({case_name: currentCaseName.value, position});
   }

   if (skinSphereOrigin !== null){
     dts.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], skinSphereOrigin[aix][0], skinSphereOrigin[aix][1], skinSphereOrigin[aix][2]).toFixed(2));
   }
   if (ribSphereOrigin !== null){
     dtr.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], ribSphereOrigin[aix][0], ribSphereOrigin[aix][1], ribSphereOrigin[aix][2]).toFixed(2));
   }
   if (nippleSphereOrigin !== null){
     dtn.value = Number(distance3D(tumourSphereOrigin[aix][0], tumourSphereOrigin[aix][1], tumourSphereOrigin[aix][2], nippleSphereOrigin[aix][0], nippleSphereOrigin[aix][1], nippleSphereOrigin[aix][2]).toFixed(2));
   }
   
   // send status to calculator component
   if (nrrdTools!.gui_states.cal_distance !== "tumour"){
    emitter.emit("SegmentationTrial:CalulatorTimerFunction", nrrdTools!.gui_states.cal_distance);
   }
   
}

const getMaskData = async (res:IToolMaskData) => {
  
  const { image, sliceId, label, clearAllFlag } = res;
  const copyImage = image.data.slice();

  const mask = [...copyImage];
  const body: IReplaceMask = {
    caseId: currentCaseName.value,
    sliceId,
    label,
    mask,
  };

  if (clearAllFlag) {
    clearMaskMeshObj(currentCaseName.value);
    sendInitMaskToBackend();
  } else {
    await sendReplaceMask(body);
  }
};

const getSliceNum = (res: IToolGetSliceNumber) => {
    const { index, contrastindex } = res;
    immediateSliceNum.value = index;
    contrastNum.value = contrastindex;
  };

const getContrastMove = (res:IToolGetMouseDragContrastMove) =>{
  const { step, towards } = res;
  if(towards === "horizental"){
    emitter.emit("Common:DragImageWindowCenter", step)
  }else if(towards === "vertical"){
    emitter.emit("Common:DragImageWindowHigh", step)
  }
}

const handleAllImagesLoaded = async (res:IToolAfterLoadImagesResponse) => {
  // step 1: get all images and meshes and store them in displaySlices and displayLoadedMeshes
  displaySlices = res.allSlices;
  displayLoadedMeshes = res.allLoadedMeshes;

  // step 2: Check current register switch bar status and store them in originSlices or registerSlices
  if (regiterSwitchBarStatus){
    registerSlices = [...displaySlices]
    regitserMeshes = [...displayLoadedMeshes]
  }else{
    originSlices = [...displaySlices]
    originMeshes = [...displayLoadedMeshes]
  }

  // step 3: config nav bar slider
  initSliceIndex.value = nrrdTools!.getCurrentSliceIndex();
  max.value = nrrdTools!.getMaxSliceNum()[1];

  // step 4: config contrast gui folder and NrrdImageCtl.vue Contrast Image States
  const selectedState: TContrastSelected = {};
  for (let i = 0; i < displaySlices.length; i++) {
    if (i == 0) {
      selectedState["pre"] = true;
    } else {
      const key = "contrast" + i;
      selectedState[key] = true;
    }
  }
  // step 4.1: update GUI
  setUpGuiAfterLoading();
  // step 4.2: send contrast name with states to NrrdImageCtl.vue
  emitter.emit("Segmentation:ContrastImageStates", selectedState);

  // step 5: tell all components that all images are loaded and give the guiSettings
  tellAllRelevantComponentsImagesLoaded();

  // step 6: only for GUI, remove duplicate folder children
  Copper.removeGuiFolderChilden(selectedContrastFolder);
  for (let i = 0; i < displaySlices.length; i++) {
    let name = "";
    i === 0 ? (name = "pre") : (name = "contrast" + i);
    selectedContrastFolder.add(selectedState, name).onChange((flag) => {
      onContrastSelected(flag, i);
    });
  }
};


// Core functions for this component
/**
 *
 * @param flag [boolean] the effect contrast state, true: add, flase: remove
 * @param i [number] the effect contrast order number
 */

function onContrastSelected(flag: boolean, i: number) {
  if (flag) {
    currentCaseContractsCount.value += 1;
    nrrdTools!.addSkip(i);
  } else {
    currentCaseContractsCount.value -= 1;
    nrrdTools!.removeSkip(i);
  }
  const maxNum = nrrdTools!.getMaxSliceNum()[1];
  if (maxNum) {
    max.value = maxNum;
    const { currentIndex, contrastIndex } =
      nrrdTools!.getCurrentSlicesNumAndContrastNum();

    immediateSliceNum.value = currentIndex;
    contrastNum.value = contrastIndex + 1;
  }
}

async function onCaseSwitched(casename: string) {
  // default every time load register image first, when case switched
  regiterSwitchBarStatus = true;

  // step 1: start animation
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Saving masks data, please wait......");

  // step 2: revoke regsiter and origin images urls
  revokeCaseUrls(originUrls);
  revokeCaseUrls(regiterUrls);
  originUrls.nrrdUrls.length = 0;
  regiterUrls.nrrdUrls.length = 0;
  originUrls.jsonUrl = "";
  regiterUrls.jsonUrl = "";

  // step 3: clear origin and register slices array
  originSlices.length = 0;
  registerSlices.length = 0;
  // revoke App all urls, need to modify later
  revokeAppUrls(loadedUrls);
  loadedUrls = {};

  // step 4: set current case name
  currentCaseName.value = casename;
  // step 5: update init data
  await getInitData();

  // step 6: start to get nrrd urls
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Prepare Nrrd files, please wait......");
  const requests = findRequestUrls(
    allCasesDetails.value?.details as Array<IDetails>,
    currentCaseName.value,
    "registration"
  );
  await getNrrdAndJsonFileUrls(requests);

  if (!!caseUrls.value) {
    regiterUrls = caseUrls.value as ICaseUrls;
    // trigger the left core ready to load function
    currentCaseContrastUrls.value = caseUrls.value.nrrdUrls;
    loadedUrls[currentCaseName.value] = caseUrls.value;
    const details = allCasesDetails.value?.details;
    emitter.emit("Segmentation:CaseDetails", {
      currentCaseId:currentCaseName.value,
      details,
      maskNrrd: !!currentCaseContrastUrls.value[1]?currentCaseContrastUrls.value[1]:currentCaseContrastUrls.value[0],
    });
  }
  // when switch case, load mask data
  loadMask.value = true;
  // tell nav bar file count
  currentCaseContractsCount.value = currentCaseContrastUrls.value.length;
}

async function onRegistedStateChanged(isShowRegisterImage: boolean) {

  switchRegCheckBoxStatus(regCkeckbox.domElement, "none", "0.5");
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Prepare and Loading data, please wait......");
  let sendToRightContrstUrl = "";

  if (!isShowRegisterImage) {
    // load origin images
    regiterSwitchBarStatus = false;

    // step 1: check is there origin slices are loaded in originSlices array
    if (originSlices.length > 0) {
      displaySlices = [...originSlices];
      displayLoadedMeshes = [...originMeshes];
      nrrdTools!.switchAllSlicesArrayData(displaySlices);
    }else{
      // step 2: if there is no origin slices
      const requests = findRequestUrls(
        allCasesDetails.value?.details as Array<IDetails>,
        currentCaseName.value,
        "origin"
      );
      await getNrrdAndJsonFileUrls(requests);
      if (!!caseUrls.value) {
        originUrls = caseUrls.value as ICaseUrls;
        // trigger the left core ready to load function
        currentCaseContrastUrls.value = caseUrls.value.nrrdUrls; 
      }
    }
    sendToRightContrstUrl = originUrls.nrrdUrls[1]?originUrls.nrrdUrls[1]:originUrls.nrrdUrls[0];
  } else {
    regiterSwitchBarStatus = true;
    displaySlices = [...registerSlices];
    displayLoadedMeshes = [...regitserMeshes];
    nrrdTools!.switchAllSlicesArrayData(displaySlices);
    sendToRightContrstUrl = regiterUrls.nrrdUrls[1]?regiterUrls.nrrdUrls[1]:regiterUrls.nrrdUrls[0];
  }

  //  Finial, send loaded data to right
  emitter.emit("Segmentation:RegisterButtonStatusChanged", {
      maskNrrdMeshes: !!displayLoadedMeshes[1]?displayLoadedMeshes[1]: displayLoadedMeshes[0],
      maskSlices: !!displaySlices[1]?displaySlices[1]:displaySlices[0],
      url: sendToRightContrstUrl,
      register: isShowRegisterImage,
    });
  //  finished swicth the images, tell all component switch successfully
  tellAllRelevantComponentsImagesLoaded()

  //  disable loading animation
  switchAnimationStatus(loadingContainer!, progress!, "none");
}

function tellAllRelevantComponentsImagesLoaded(){
  const guiSettings = nrrdTools!.getGuiSettings();
  emitter.emit("Segmentation:FinishLoadAllCaseImages", guiSettings);
}

function setupGui() {
  state.switchCase = allCasesDetails.value?.names[0] as string;

  gui!
    .add(state, "switchCase", allCasesDetails.value?.names as string[])
    .onChange(async (caseId: string) => {
      await onCaseSwitched(caseId);
      setUpGuiAfterLoading();
    });

  selectedContrastFolder = gui!.addFolder("select display contrast");
}

function setUpGuiAfterLoading() {
  if (!!optsGui) {
    gui!.removeFolder(optsGui);
    optsGui = undefined;
    state.showRegisterImages = true;
  }
  optsGui = gui!.addFolder("opts");
  regCkeckbox = optsGui!.add(state, "showRegisterImages");
  regCheckboxElement = regCkeckbox.domElement.childNodes[0] as HTMLInputElement;
  regCkeckbox.onChange(async () => {
    if (regCheckboxElement.disabled) {
      state.showRegisterImages = !state.showRegisterImages;
      return;
    }

    await onRegistedStateChanged(state.showRegisterImages);
  });
  optsGui!.add(state, "release");
  optsGui!.closed = false;
}

function switchRegCheckBoxStatus(
  checkbox: HTMLElement,
  pointerEvents: "none" | "auto",
  opacity: "0.5" | "1"
) {
  const inputBox = checkbox.childNodes[0] as HTMLInputElement;
  inputBox.disabled = !inputBox.disabled;
  inputBox.readOnly = !inputBox.readOnly;
  checkbox.style.pointerEvents = pointerEvents;
  checkbox.style.opacity = opacity;
}

onUnmounted(() => {
  emitter.off("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox)
  emitter.off("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox)
  emitter.off("Common:DebugMode", emitterOnDebugMode);
  emitter.off("Common:ToggleAppTheme", emitterOnToggleAppTheme);
  emitter.off("Segementation:CaseSwitched", emitterOnCaseSwitched);
  emitter.off("Segmentation:ContrastChanged", emitterOnContrastChanged);
  emitter.off("Segmentation:RegisterImageChanged", emitteOnRegisterImageChanged);
  nrrdTools!.clear();
  currentCaseContrastUrls.value.length = 0;
  displaySlices.length = 0;
  displayLoadedMeshes.length = 0;
  originSlices.length = 0;
  registerSlices.length = 0;  
});
 
</script>

<style>
</style>
