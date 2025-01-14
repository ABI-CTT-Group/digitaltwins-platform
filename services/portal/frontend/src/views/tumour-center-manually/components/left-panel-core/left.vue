<template>
  <LeftPanelCore 
    ref="leftPanelCoreRef"
    :show-debug-panel="debug_mode" 
    :show-slice-index="true"
    :enable-upload="true"
    :show-tumour-distance-panel="showCalculatorValue"
    :show-bottom-nav-bar="panelWidth >= 600 ? true : false">
    <template #drag-to-upload>
      <Upload
        :dialog="dialog"
        @on-close-dialog="onCloseDialog"
        @get-load-files-urls="readyToLoad"
      />
    </template>
    <template #tumour-distance-panel>
      <TumourDistancePanel :dts="dts" :dtn="dtn" :dtr="dtr" />
    </template>
    <template #bottom-nav-bar>
      <NavBar
        :file-num="fileNum"
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
} from "@/models/apiTypes";
import { addNameToLoadedMeshes, findRequestUrls, customRound, distance3D } from "@/plugins/view-utils/utils-left";
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
let fileNum = ref(0);
let initSliceIndex = ref(0);
let dialog = ref(false);


let debug_mode = ref(false);


let pre_slices = ref();

let optsGui: GUI | undefined = undefined;


let allSlices: Array<any> = [];
let defaultRegAllSlices: Array<any> = [];
let originAllSlices: Array<any> = [];
let allLoadedMeshes: Array<ILoadedMeshes> = [];
let defaultRegAllMeshes: Array<ILoadedMeshes> = [];
let originAllMeshes: Array<ILoadedMeshes> = [];
let regCkeckbox: GUIController;
let allContrastUrls: Array<string> = [];
let loadedUrls: ILoadUrls = {};

let filesCount = ref(0);
let selectedContrastFolder: GUI;
let firstLoad = true;
let loadCases = true;
let loadOrigin = false;
let originRegswitcher = false;

let currentCaseId = "";
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
let coreRenderId = 0;

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

onMounted(async () => {
  nrrdTools = leftPanelCoreRef.value?.nrrdTools;
  scene = leftPanelCoreRef.value?.scene;
  loadBarMain = leftPanelCoreRef.value?.loadBarMain;
  loadingContainer = leftPanelCoreRef.value?.loadingContainer;
  progress = leftPanelCoreRef.value?.progress;
  gui = leftPanelCoreRef.value?.gui;
  baseContainer = leftPanelCoreRef.value?.baseContainer;
  
  manageEmitters();

  // get init data
  await getAllCasesDetails();
});

const readyToLoad = (urlsArray: Array<string>, name: string) => {
  fileNum.value = urlsArray.length;
  allContrastUrls = urlsArray;
  if (allContrastUrls.length > 0) {
    return new Promise<{ meshes: Array<Copper.nrrdMeshesType>; slices: any[] }>(
      (resolve, reject) => {
        loadAllNrrds(allContrastUrls, name, resolve, reject);
      }
    );
  }
};
const onSaveMask = async (flag: boolean) => {
  if (flag && nrrdTools!.protectedData.maskData.paintImages.z.length > 0) {
    switchAnimationStatus("flex", "Saving masks data, please wait......");
    await sendSaveMask(currentCaseId);
    switchAnimationStatus("none");
    emitter.emit("Segmentation:SyncTumourModelButtonClicked", true);
  }
};
const onOpenDialog = (flag: boolean) => {
  dialog.value = flag;
};
const onCloseDialog = (flag: boolean) => {
  dialog.value = flag;
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
      caseId: currentCaseId,
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
  switchAnimationStatus("flex", "Loading masks data......");

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
  if (loadedUrls[currentCaseId]) {
    if (allCasesDetails.value) {
      const currentCaseDetail = findCurrentCase(
        allCasesDetails.value.details,
        currentCaseId
      );
      if (currentCaseDetail.masked) {
        if (caseUrls.value)
          loadJsonMasks(loadedUrls[currentCaseId].jsonUrl as string);
      } else {
        sendInitMaskToBackend();
      }
    }
  }
  setTimeout(() => {
    // wait for loading mask, give a delay before user start operate
    switchAnimationStatus("none");
  }, 1000);
};

const switchAnimationStatus = (status: "flex" | "none", text?: string) => {
  loadingContainer!.style.display = status;
  !!text && (progress!.innerText = text);
};

const getSphereData = async (sphereOrigin: number[], sphereRadius: number) => {
  const sphereData: ISaveSphere = {
    caseId: currentCaseId,
    sliceId: sphereOrigin[2],
    origin: nrrdTools!.nrrd_states.spaceOrigin,
    spacing: nrrdTools!.nrrd_states.voxelSpacing,
    sphereRadiusMM: sphereRadius,
    sphereOriginMM: [sphereOrigin[0],sphereOrigin[1],sphereOrigin[2]*nrrdTools!.nrrd_states.voxelSpacing[2]],
  };

  emitter.emit("SegmentationTrial:DrawSphereFunction", sphereData);

  await sendSaveSphere(sphereData);
};


const getCalculateSpherePositionsData = async (tumourSphereOrigin:Copper.ICommXYZ | null, skinSphereOrigin:Copper.ICommXYZ | null, ribSphereOrigin:Copper.ICommXYZ | null, nippleSphereOrigin:Copper.ICommXYZ | null, aix:"x"|"y"|"z")=>{
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
    await useSaveTumourPosition({case_name: currentCaseId, position});
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

const getMaskData = async (
  image: ImageData,
  sliceId: number,
  label: string,
  width: number,
  height: number,
  clearAllFlag?: boolean
) => {
  const copyImage = image.data.slice();

  const mask = [...copyImage];
  const body: IReplaceMask = {
    caseId: currentCaseId,
    sliceId,
    label,
    mask,
  };

  if (clearAllFlag) {
    clearMaskMeshObj(currentCaseId);
    sendInitMaskToBackend();
  } else {
    await sendReplaceMask(body);
  }
};

const getContrastMove = (step:number, towards:"horizental"|"vertical") =>{
  if(towards === "horizental"){
    emitter.emit("Common:DragImageWindowCenter", step)
  }else if(towards === "vertical"){
    emitter.emit("Common:DragImageWindowHigh", step)
  }
  
}

watchEffect(() => {
  if (
    filesCount.value != 0 &&
    allSlices.length != 0 &&
    filesCount.value === allContrastUrls.length
  ) {
    console.log("All files ready!");

    allSlices.sort((a: any, b: any) => {
      return a.order - b.order;
    });
    allLoadedMeshes.sort((a: any, b: any) => {
      return a.order - b.order;
    });

    if(originRegswitcher){ 
      nrrdTools!.switchAllSlicesArrayData(allSlices);
      if(loadOrigin) {
        loadOrigin = false;
        if (originAllSlices.length === 0) {
          originAllSlices = [...allSlices];
          originAllMeshes = [...allLoadedMeshes];
        }
      }
      setTimeout(
          () => switchRegCheckBoxStatus(regCkeckbox.domElement, "auto", "1"),
          1000
        );
  } else {
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
        nrrdTools!.draw({ getMaskData, getSphereData, getCalculateSpherePositionsData});
        nrrdTools!.setupGUI(gui as GUI);
        nrrdTools!.enableContrastDragEvents(getContrastMove)
        coreRenderId = scene?.addPreRenderCallbackFunction(nrrdTools!.start) as number;
        setUpGuiAfterLoading();
        // xyz: 84 179 74
        // emitter.emit("loadcalculatortumour", nrrdTools);
      } else {
        nrrdTools!.redrawMianPreOnDisplayCanvas();
      }

      if (loadCases) {
        setMaskData();
      }

      max.value = nrrdTools!.getMaxSliceNum()[1];

      const selectedState: selecedType = {};

      for (let i = 0; i < allSlices.length; i++) {
        if (i == 0) {
          selectedState["pre"] = true;
        } else {
          const key = "contrast" + i;
          selectedState[key] = true;
        }
      }

      // send contrast name with states to NrrdImageCtl.vue
      emitter.emit("Segmentation:ContrastImageStates", selectedState);

      Copper.removeGuiFolderChilden(selectedContrastFolder);
      for (let i = 0; i < allSlices.length; i++) {
        let name = "";
        i === 0 ? (name = "pre") : (name = "contrast" + i);
        selectedContrastFolder.add(selectedState, name).onChange((flag) => {
          onContrastSelected(flag, i);
        });
      }
    }
    setTimeout(() => {
      initSliceIndex.value = 0;
      filesCount.value = 0;
      const guiSettings = nrrdTools!.getGuiSettings();
      emitter.emit("Segmentation:FinishLoadAllCaseImages", guiSettings);
    }, 1000);
    firstLoad = false;
    loadCases = false;
    originRegswitcher = false;
    switchAnimationStatus("none");
  }
});



const loadAllNrrds = (
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
        console.log(nrrdSlices);
        
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

/**
 *
 * @param flag [boolean] the effect contrast state, true: add, flase: remove
 * @param i [number] the effect contrast order number
 */

function onContrastSelected(flag: boolean, i: number) {
  if (flag) {
    fileNum.value += 1;
    nrrdTools!.addSkip(i);
  } else {
    fileNum.value -= 1;
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
  switchAnimationStatus("flex", "Saving masks data, please wait......");
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

  currentCaseId = casename;
  // update init data
  await getAllCasesDetails();

  if (loadedUrls[casename]) {
    switchAnimationStatus(
      "flex",
      "Prepare and Loading masks data, please wait......"
    );
    URL.revokeObjectURL(loadedUrls[casename].jsonUrl);
    await getMaskDataBackend(casename);
    loadedUrls[casename].jsonUrl = maskBackend.value;
    allContrastUrls = loadedUrls[casename].nrrdUrls;
    if (!!caseUrls.value) {
      caseUrls.value.nrrdUrls = allContrastUrls;
    }
  } else {
    
    switchAnimationStatus("flex", "Prepare Nrrd files, please wait......");
    // await getCaseFileUrls(value);
    const requests = findRequestUrls(
      allCasesDetails.value?.details as Array<IDetails>,
      currentCaseId,
      "registration"
    );
    await getNrrdAndJsonFileUrls(requests);

    if (!!caseUrls.value) {
      regUrls.value = caseUrls.value as ICaseUrls;
      allContrastUrls = caseUrls.value.nrrdUrls;
      loadedUrls[currentCaseId] = caseUrls.value;
      const details = allCasesDetails.value?.details;
      console.log(allContrastUrls);
      
      emitter.emit("Segmentation:CaseDetails", {
        currentCaseId,
        details,
        maskNrrd: !!allContrastUrls[1]?allContrastUrls[1]:allContrastUrls[0],
      });
    }
  }

  readyToLoad(allContrastUrls, "registration");
  loadCases = true;
}

async function onRegistedStateChanged(isShowRegisterImage: boolean) {

  originRegswitcher = true;
  switchRegCheckBoxStatus(regCkeckbox.domElement, "none", "0.5");
  switchAnimationStatus("flex", "Prepare and Loading data, please wait......");

  if (!isShowRegisterImage) {
    // show origin
    loadOrigin = true;
    if (originAllSlices.length > 0) {
      allSlices = [...originAllSlices];
      allLoadedMeshes = [...originAllMeshes];
      filesCount.value = allContrastUrls.length;
      emitter.emit("Segmentation:RegisterButtonStatusChanged", {
        maskNrrdMeshes: !!originAllMeshes[1]?originAllMeshes[1]: originAllMeshes[0],
        maskSlices: !!originAllSlices[1]?originAllSlices[1]:originAllSlices[0],
        url: !!allContrastUrls[1]?allContrastUrls[1]:allContrastUrls[0],
        register: isShowRegisterImage,
      });
      return;
    }

    if (
      !(!!originUrls.value?.nrrdUrls && originUrls.value?.nrrdUrls.length > 0)
    ) {
      const requests = findRequestUrls(
        allCasesDetails.value?.details as Array<IDetails>,
        currentCaseId,
        "origin"
      );
      await getNrrdAndJsonFileUrls(requests);
      originUrls.value = caseUrls.value as ICaseUrls;
    }

    if (!!originUrls.value?.nrrdUrls && originUrls.value?.nrrdUrls.length > 0) {
      allContrastUrls = originUrls.value.nrrdUrls;
      readyToLoad(allContrastUrls, "origin")?.then((data) => {
        emitter.emit("Segmentation:RegisterButtonStatusChanged", {
          maskNrrdMeshes: data.meshes[1],
          maskSlices: data.slices[1],
          url:  !!allContrastUrls[1]?allContrastUrls[1]:allContrastUrls[0],
          register: isShowRegisterImage,
        });
      });
    }
  } else {
    loadOrigin = false;
    if (defaultRegAllSlices.length > 0) {
      allContrastUrls = regUrls.value.nrrdUrls;
      allSlices = [...defaultRegAllSlices];
      allLoadedMeshes = [...defaultRegAllMeshes];
      filesCount.value = allContrastUrls.length;
      emitter.emit("Segmentation:RegisterButtonStatusChanged", {
        maskNrrdMeshes: !!defaultRegAllMeshes[1]?defaultRegAllMeshes[1]:defaultRegAllMeshes[0],
        maskSlices: !!defaultRegAllSlices[1]?defaultRegAllSlices[1]:defaultRegAllSlices[0],
        url:  !!allContrastUrls[1]?allContrastUrls[1]:allContrastUrls[0],
        register: isShowRegisterImage,
      });
      return;
    }
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
  allContrastUrls.length = 0;
  allSlices.length = 0;
  allLoadedMeshes.length = 0;
  originAllSlices.length = 0;
  defaultRegAllSlices.length = 0;
  originAllMeshes.length = 0;
  defaultRegAllMeshes.length = 0;
  scene?.removePreRenderCallbackFunction(coreRenderId);
});
 
</script>

<style>

</style>
