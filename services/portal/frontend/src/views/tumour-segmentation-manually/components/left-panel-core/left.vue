<template>
  <LeftPanelCore 
    ref="leftPanelCoreRef"
    v-model:load-mask="loadMask"
    :show-debug-panel="debug_mode" 
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



import { onMounted, ref, watchEffect, onUnmounted, watch } from "vue";
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
  IToolGetSliceNumber
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
  revokeRegisterNrrdImages,
  getEraserUrlsForOffLine,
  getCursorUrlsForOffLine,
} from "@/plugins/view-utils/tools";
import emitter from "@/plugins/custom-emitter";
import { convertInitMaskData } from "@/plugins/worker";
import { switchAnimationStatus } from "@/components/view-components/leftCoreUtils";
import { get } from "http";


type Props = {
  panelWidth: number;
};

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
let filesCount = ref(0);
let initSliceIndex = ref(0);
let dialog = ref(false);


let debug_mode = ref(false);

let optsGui: GUI | undefined = undefined;


let allSlices: Array<any> = [];
let allLoadedMeshes: Array<ILoadedMeshes> = [];

let defaultRegAllSlices: Array<any> = [];
let originAllSlices: Array<any> = [];
let defaultRegAllMeshes: Array<ILoadedMeshes> = [];
let originAllMeshes: Array<ILoadedMeshes> = [];
let regCkeckbox: GUIController;
let currentCaseContrastUrls = ref<Array<string>>([]);
let loadedUrls: ILoadUrls = {};


let selectedContrastFolder: GUI;

let loadMask = ref(true);
let loadOrigin = false;
let originRegswitcher = false;

let currentCaseName = ref("");
let regCheckboxElement: HTMLInputElement;

let dts = ref(0);
let dtn = ref(0);
let dtr = ref(0);


let state = {
  showContrast: false,
  switchCase: "",
  showRegisterImages: true,
  release: () => {
    revokeAppUrls(loadedUrls);
    loadedUrls = {};
  },
};

type selecedType = {
  [key: string]: boolean;
};



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

let originUrls = ref<ICaseUrls>({ nrrdUrls: [], jsonUrl: "" });
let regUrls = ref<ICaseUrls>({ nrrdUrls: [], jsonUrl: "" });


const showCalculatorValue = ref(false);


withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

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
  debug_mode.value = flag;
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

const onFinishedCopperInit = (copperInitData:ILeftCoreCopperInit)=>{

  nrrdTools = copperInitData.nrrdTools;
  scene = copperInitData.scene;
  console.log(nrrdTools.getGuiSettings());
}

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


const onSaveMask = async (flag: boolean) => {
  if (flag && nrrdTools!.protectedData.maskData.paintImages.z.length > 0) {
    switchAnimationStatus(loadingContainer!, progress!, "flex", "Saving masks data, please wait......");
    await sendSaveMask(currentCaseName.value);
    switchAnimationStatus(loadingContainer!, progress!, "none");
    emitter.emit("Segmentation:SyncTumourModelButtonClicked", true);
  }
};
const onOpenDialog = (flag: boolean) => {
  dialog.value = flag;
};
const onCloseDialog = (flag: boolean) => {
  dialog.value = flag;
};
const handleUploadFiles = (urls: string[]) =>{
  currentCaseContrastUrls.value = urls;
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
const resetMainAreaSize = (factor: number) => {
  nrrdTools!.setMainAreaSize(factor);
};

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

const getContrastMove = (step:number, towards:"horizental"|"vertical") =>{
  if(towards === "horizental"){
    emitter.emit("Common:DragImageWindowCenter", step)
  }else if(towards === "vertical"){
    emitter.emit("Common:DragImageWindowHigh", step)
  }
}

const handleAllImagesLoaded = async (res:IToolAfterLoadImagesResponse) => {
  allSlices = res.allSlices;
  allLoadedMeshes = res.allLoadedMeshes;
  const selectedState: selecedType = {};

  initSliceIndex.value = nrrdTools!.getCurrentSliceIndex();
  max.value = nrrdTools!.getMaxSliceNum()[1];

  for (let i = 0; i < allSlices.length; i++) {
    if (i == 0) {
      selectedState["pre"] = true;
    } else {
      const key = "contrast" + i;
      selectedState[key] = true;
    }
  }
  setUpGuiAfterLoading();
  // send contrast name with states to NrrdImageCtl.vue
  emitter.emit("Segmentation:ContrastImageStates", selectedState);
  const guiSettings = nrrdTools!.getGuiSettings();
  emitter.emit("Segmentation:FinishLoadAllCaseImages", guiSettings);

  Copper.removeGuiFolderChilden(selectedContrastFolder);
  for (let i = 0; i < allSlices.length; i++) {
    let name = "";
    i === 0 ? (name = "pre") : (name = "contrast" + i);
    selectedContrastFolder.add(selectedState, name).onChange((flag) => {
      onContrastSelected(flag, i);
    });
  }

  // initSliceIndex.value = 0;
};


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
  
  loadOrigin = false;
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Saving masks data, please wait......");
  // revoke the regsiter images
  if (!!originUrls.value && originUrls.value.nrrdUrls.length > 0) {
    revokeRegisterNrrdImages(originUrls.value.nrrdUrls);
    originUrls.value.nrrdUrls.length = 0;
  }
  originAllSlices.length = 0;
  defaultRegAllSlices.length = 0;
  originAllMeshes.length = 0;
  defaultRegAllMeshes.length = 0;
  // temprary disable this function
  revokeAppUrls(loadedUrls);
  loadedUrls = {};

  currentCaseName.value = casename;
  // update init data
  await getInitData();

  if (loadedUrls[casename]) {
    switchAnimationStatus(
      loadingContainer!, progress!, 
      "flex",
      "Prepare and Loading masks data, please wait......"
    );
    URL.revokeObjectURL(loadedUrls[casename].jsonUrl);
    await getMaskDataBackend(casename);
    loadedUrls[casename].jsonUrl = maskBackend.value;
    currentCaseContrastUrls.value = loadedUrls[casename].nrrdUrls;
    if (!!caseUrls.value) {
      caseUrls.value.nrrdUrls = currentCaseContrastUrls.value;
    }
  } else {
    
    switchAnimationStatus(loadingContainer!, progress!, "flex", "Prepare Nrrd files, please wait......");
    // await getCaseFileUrls(value);
    const requests = findRequestUrls(
      allCasesDetails.value?.details as Array<IDetails>,
      currentCaseName.value,
      "registration"
    );
    await getNrrdAndJsonFileUrls(requests);

    if (!!caseUrls.value) {
      regUrls.value = caseUrls.value as ICaseUrls;
      currentCaseContrastUrls.value = caseUrls.value.nrrdUrls;
      loadedUrls[currentCaseName.value] = caseUrls.value;
      const details = allCasesDetails.value?.details;
      emitter.emit("Segmentation:CaseDetails", {
        currentCaseId:currentCaseName.value,
        details,
        maskNrrd: !!currentCaseContrastUrls.value[1]?currentCaseContrastUrls.value[1]:currentCaseContrastUrls.value[0],
      });
    }
  }

  // readyToLoad("registration");
  loadMask.value = true;
  currentCaseContractsCount.value = currentCaseContrastUrls.value.length;
}

async function onRegistedStateChanged(isShowRegisterImage: boolean) {

  originRegswitcher = true;
  switchRegCheckBoxStatus(regCkeckbox.domElement, "none", "0.5");
  switchAnimationStatus(loadingContainer!, progress!, "flex", "Prepare and Loading data, please wait......");

  if (!isShowRegisterImage) {
    // show origin
    loadOrigin = true;
    if (originAllSlices.length > 0) {
      allSlices = [...originAllSlices];
      allLoadedMeshes = [...originAllMeshes];
      filesCount.value = currentCaseContrastUrls.value.length;
      emitter.emit("Segmentation:RegisterButtonStatusChanged", {
        maskNrrdMeshes: !!originAllMeshes[1]?originAllMeshes[1]: originAllMeshes[0],
        maskSlices: !!originAllSlices[1]?originAllSlices[1]:originAllSlices[0],
        url: !!currentCaseContrastUrls.value[1]?currentCaseContrastUrls.value[1]:currentCaseContrastUrls.value[0],
        register: isShowRegisterImage,
      });
      return;
    }

    if (
      !(!!originUrls.value?.nrrdUrls && originUrls.value?.nrrdUrls.length > 0)
    ) {
      const requests = findRequestUrls(
        allCasesDetails.value?.details as Array<IDetails>,
        currentCaseName.value,
        "origin"
      );
      await getNrrdAndJsonFileUrls(requests);
      originUrls.value = caseUrls.value as ICaseUrls;
    }

    // if (!!originUrls.value?.nrrdUrls && originUrls.value?.nrrdUrls.length > 0) {
    //   currentCaseContrastUrls = originUrls.value.nrrdUrls;
    //   readyToLoad("origin")?.then((data) => {
    //     emitter.emit("Segmentation:RegisterButtonStatusChanged", {
    //       maskNrrdMeshes: data.meshes[1],
    //       maskSlices: data.slices[1],
    //       url:  !!currentCaseContrastUrls[1]?currentCaseContrastUrls[1]:currentCaseContrastUrls[0],
    //       register: isShowRegisterImage,
    //     });
    //   });
    // }
  } else {
    loadOrigin = false;
    // if (defaultRegAllSlices.length > 0) {
    //   currentCaseContrastUrls = regUrls.value.nrrdUrls;
    //   allSlices = [...defaultRegAllSlices];
    //   allLoadedMeshes = [...defaultRegAllMeshes];
    //   filesCount.value = currentCaseContrastUrls.length;
    //   emitter.emit("Segmentation:RegisterButtonStatusChanged", {
    //     maskNrrdMeshes: !!defaultRegAllMeshes[1]?defaultRegAllMeshes[1]:defaultRegAllMeshes[0],
    //     maskSlices: !!defaultRegAllSlices[1]?defaultRegAllSlices[1]:defaultRegAllSlices[0],
    //     url:  !!currentCaseContrastUrls[1]?currentCaseContrastUrls[1]:currentCaseContrastUrls[0],
    //     register: isShowRegisterImage,
    //   });
    //   return;
    // }
  }
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
  allSlices.length = 0;
  allLoadedMeshes.length = 0;
  originAllSlices.length = 0;
  defaultRegAllSlices.length = 0;
  originAllMeshes.length = 0;
  defaultRegAllMeshes.length = 0;
  
});
 
</script>

<style>
</style>
