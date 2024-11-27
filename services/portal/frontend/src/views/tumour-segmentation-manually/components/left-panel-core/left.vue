<template>
  <div id="bg" ref="base_container" class="dark guide-left-panel">
    <div v-show="debug_mode" ref="c_gui" class="left_gui"></div>
    <div ref="canvas_container" class="canvas_container"></div>
    <div ref="slice_index_container" class="copper3d_sliceNumber">
      Tumour Segmentation Panel
    </div>

    <Upload
      :dialog="dialog"
      @on-close-dialog="onCloseDialog"
      @get-load-files-urls="readyToLoad"
    ></Upload>

    <!-- <div v-show="showCalculatorValue" class="left-value-panel mt-2">
      <div class="dts"><span>DTS:</span> <span>{{ 0 }} mm</span></div>
      <div class="dtr"><span>DTR:</span> <span>{{ 0 }} mm</span></div>
      <div class="dtn">
        <span>DTN:</span> <span>{{ 0 }} mm</span>
      </div>
    </div> -->
    <v-card v-show="showCalculatorValue" class="left-value-panel mt-2">
      <div class="dts"><span>DTS:</span> <span>{{ dts }} mm</span></div>
      <div class="dtn"><span>DTN:</span> <span>{{ dtn }} mm</span></div>
      <div class="dtr"><span>DTR:</span> <span>{{ dtr }} mm</span></div>
    </v-card>
  </div>
  <div
    v-show="panelWidth >= 600 ? true : false"
    class="nav_bar_left_container"
    ref="nav_bar_left_container"
  >
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
    ></NavBar>
  </div>
</template>
<script setup lang="ts">
import { GUI, GUIController } from "dat.gui";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
// import * as Copper from "@/ts/index";
import loadingGif from "@/assets/loading.svg";

import NavBar from "@/components/commonBar/NavBar.vue";
import Upload from "@/components/commonBar/Upload.vue";
import { onMounted, ref, watchEffect } from "vue";
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
import { addNameToLoadedMeshes, findRequestUrls } from "./utils-left";
import {
  useFileCountStore,
  useInitMarksStore,
  useReplaceMarksStore,
  useSaveSphereStore,
  useSaveMasksStore,
  useMaskStore,
  useClearMaskMeshStore,
  useNrrdCaseFileUrlsWithOrderStore,
} from "@/store/app";
import {
  findCurrentCase,
  revokeAppUrls,
  revokeRegisterNrrdImages,
  getEraserUrlsForOffLine,
  getCursorUrlsForOffLine,
} from "@/views/tumour-segmentation-manually/components/tools";
import emitter from "@/plugins/bus";
import { convertInitMaskData } from "@/plugins/worker";

type Props = {
  panelWidth: number;
};

let appRenderer: Copper.copperRenderer;
let max = ref(0);
let immediateSliceNum = ref(0);
let contrastNum = ref(0);
let fileNum = ref(0);
let initSliceIndex = ref(0);
let dialog = ref(false);

let base_container = ref<HTMLDivElement>();
let c_gui = ref<HTMLDivElement>();
let canvas_container = ref<HTMLDivElement>();
let nav_bar_left_container = ref<HTMLDivElement>();
let slice_index_container = ref<HTMLDivElement>();
let debug_mode = ref(false);

let scene: Copper.copperScene | undefined;
let pre_slices = ref();

let gui = new GUI({ width: 300, autoPlace: false });
let optsGui: GUI | undefined = undefined;
let nrrdTools: Copper.NrrdTools;
let loadBarMain: Copper.loadingBarType;
let loadingContainer: HTMLDivElement, progress: HTMLDivElement;
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

let showNavToolsBar = ref(true);

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

let toolsState: any;

const { cases } = storeToRefs(useFileCountStore());
const { getFilesNames } = useFileCountStore();
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

const eraserUrls = getEraserUrlsForOffLine();
const cursorUrls = getCursorUrlsForOffLine();

const showCalculatorValue = ref(false);

withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

function onEmitter() {
  emitter.on("open_calculate_box", (val)=>{
    showCalculatorValue.value = true
  })
  emitter.on("close_calculate_box", (val)=>{
    showCalculatorValue.value = false
  })

  emitter.on("show_debug_mode", (flag) => {
    debug_mode.value = flag as boolean;
  });

  // emitter.on("resize-left-right-panels", (effects) => {
  //   console.log((effects as any).effectPanelSize);

  //   // if ((effects as any).panel === "left") {
  //   //   if ((effects as any).effectPanelSize < 600) {
  //   //     showNavToolsBar.value = false;
  //   //     return;
  //   //   }
  //   // }
  //   // showNavToolsBar.value = true;
  // });

  emitter.on("toggleTheme", () => {
    base_container.value?.classList.toggle("dark");
  });
  emitter.on("leftFullScreen", (flag) => {
    if (flag) {
      (nav_bar_left_container.value as HTMLDivElement).style.width = "90%";
    } else {
      (nav_bar_left_container.value as HTMLDivElement).style.width = "60%";
    }
  });
  // emitter.on("containerHight", (h) => {
  //   (base_container.value as HTMLDivElement).style.height = `${h}vh`;
  // });
  emitter.on("caseswitched", async (casename) => {
    await onCaseSwitched(casename as string);
  });

  emitter.on("contrastselected", (result) => {
    const { contrastState, order } = result as any;
    onContrastSelected(contrastState, order);
  });

  emitter.on("registerimagechanged", async (result) => {
    await onRegistedStateChanged(result as boolean);
  });
}

onMounted(async () => {
  onEmitter();

  await getInitData();
  c_gui.value?.appendChild(gui.domElement);

  appRenderer = new Copper.copperRenderer(
    base_container.value as HTMLDivElement,
    {
      guiOpen: false,
      alpha: true,
    }
  );

  nrrdTools = new Copper.NrrdTools(canvas_container.value as HTMLDivElement);
  nrrdTools.setDisplaySliceIndexPanel(
    slice_index_container.value as HTMLDivElement
  );
  // for offline working

  // nrrdTools.setBaseCanvasesSize(1.5);
  nrrdTools.setEraserUrls(eraserUrls);
  nrrdTools.setPencilIconUrls(cursorUrls);
  // nrrdTools.setMainAreaSize(3);

  // sphere plan b
  toolsState = nrrdTools.getNrrdToolsSettings();
  // toolsState.spherePlanB = false;

  loadBarMain = Copper.loading(loadingGif);

  loadingContainer = loadBarMain.loadingContainer;
  progress = loadBarMain.progress;

  (canvas_container.value as HTMLDivElement).appendChild(
    loadBarMain.loadingContainer
  );

  document.addEventListener("keydown", (e) => {
    if (e.code === "KeyF") {
      Copper.fullScreenListenner(base_container.value as HTMLDivElement);
    }
  });

  setupGui();
  setupCopperScene("nrrd_tools");
  appRenderer.animate();
});

async function getInitData() {
  await getFilesNames();
}

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
  if (flag && nrrdTools.protectedData.maskData.paintImages.z.length > 0) {
    switchAnimationStatus("flex", "Saving masks data, please wait......");
    await sendSaveMask(currentCaseId);
    switchAnimationStatus("none");
    emitter.emit("syncTumourObjMesh", true);
  }
};

const onOpenDialog = (flag: boolean) => {
  dialog.value = flag;
};
const onCloseDialog = (flag: boolean) => {
  dialog.value = flag;
};

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
const resetMainAreaSize = (factor: number) => {
  nrrdTools.setMainAreaSize(factor);
};

const sendInitMaskToBackend = async () => {
  // const masksData = nrrdTools.paintImages.z;
  const rawMaskData = nrrdTools.getMaskData();
  const masksData = {
    label1: rawMaskData.paintImagesLabel1.z,
    label2: rawMaskData.paintImagesLabel2.z,
    label3: rawMaskData.paintImagesLabel3.z,
  };
  const dimensions = nrrdTools.getCurrentImageDimension();
  const len = rawMaskData.paintImages.z.length;
  const width = dimensions[0];
  const height = dimensions[1];
  const voxelSpacing = nrrdTools.getVoxelSpacing();
  const spaceOrigin = nrrdTools.getSpaceOrigin();
  
  
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
      nrrdTools.setMasksData(data, loadBarMain);
    }
  };
  xhr.send();
};

const setMaskData = () => {
  if (loadedUrls[currentCaseId]) {
    if (cases.value) {
      const currentCaseDetail = findCurrentCase(
        cases.value.details,
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
  loadingContainer.style.display = status;
  !!text && (progress.innerText = text);
};

const getSphereData = async (sphereOrigin: number[], sphereRadius: number) => {
  const sphereData: ISaveSphere = {
    caseId: currentCaseId,
    sliceId: sphereOrigin[2],
    origin: nrrdTools.nrrd_states.spaceOrigin,
    spacing: nrrdTools.nrrd_states.voxelSpacing,
    sphereRadiusMM: sphereRadius,
    sphereOriginMM: [sphereOrigin[0],sphereOrigin[1],sphereOrigin[2]*nrrdTools.nrrd_states.voxelSpacing[2]],
  };

  emitter.emit("drawSphere",sphereData);

  await sendSaveSphere(sphereData);
};

function distance3D(x1:number, y1:number, z1:number, x2:number, y2:number, z2:number) {
    let dx = x2 - x1;
    let dy = y2 - y1;
    let dz = z2 - z1;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

const getCalculateSpherePositionsData = (tumourSphereOrigin:Copper.ICommXYZ, skinSphereOrigin:Copper.ICommXYZ, ribSphereOrigin:Copper.ICommXYZ, nippleSphereOrigin:Copper.ICommXYZ, aix:"x"|"y"|"z")=>{
   if(tumourSphereOrigin === null) return;

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
   if (nrrdTools.gui_states.cal_distance !== "tumour"){
    emitter.emit("calculator timer", nrrdTools.gui_states.cal_distance);
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
    emitter.emit("dragImageWindowCenter", step)
  }else if(towards === "vertical"){
    emitter.emit("dragImageWindowHigh", step)
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
      nrrdTools.switchAllSlicesArrayData(allSlices);
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
        nrrdTools.draw({ getMaskData, getSphereData, getCalculateSpherePositionsData});
        nrrdTools.setupGUI(gui);
        nrrdTools.enableContrastDragEvents(getContrastMove)
        scene?.addPreRenderCallbackFunction(nrrdTools.start);
        setUpGuiAfterLoading();
        // xyz: 84 179 74
        emitter.emit("loadcalculatortumour", nrrdTools);
      } else {
        nrrdTools.redrawMianPreOnDisplayCanvas();
      }

      if (loadCases) {
        setMaskData();
      }

      max.value = nrrdTools.getMaxSliceNum()[1];

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
      emitter.emit("setcontrastnames", selectedState);

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
      const guiSettings = nrrdTools.getGuiSettings();
      emitter.emit("finishloadcases", guiSettings);
    }, 1000);
    firstLoad = false;
    loadCases = false;
    originRegswitcher = false;
    switchAnimationStatus("none");
  }
});

async function setupCopperScene(name: string) {
  scene = appRenderer.getSceneByName(name) as Copper.copperScene;
  if (scene == undefined) {
    scene = appRenderer.createScene(name) as Copper.copperScene;
    if (scene) {
      appRenderer.setCurrentScene(scene);
    }
  }
}

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

/**
 *
 * @param flag [boolean] the effect contrast state, true: add, flase: remove
 * @param i [number] the effect contrast order number
 */

function onContrastSelected(flag: boolean, i: number) {
  if (flag) {
    fileNum.value += 1;
    nrrdTools.addSkip(i);
  } else {
    fileNum.value -= 1;
    nrrdTools.removeSkip(i);
  }
  const maxNum = nrrdTools.getMaxSliceNum()[1];
  if (maxNum) {
    max.value = maxNum;
    const { currentIndex, contrastIndex } =
      nrrdTools.getCurrentSlicesNumAndContrastNum();

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
  await getInitData();

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
      cases.value?.details as Array<IDetails>,
      currentCaseId,
      "registration"
    );
    await getNrrdAndJsonFileUrls(requests);

    if (!!caseUrls.value) {
      regUrls.value = caseUrls.value as ICaseUrls;
      allContrastUrls = caseUrls.value.nrrdUrls;
      loadedUrls[currentCaseId] = caseUrls.value;
      const details = cases.value?.details;
      emitter.emit("casename", {
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
      emitter.emit("showRegBtnToRight", {
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
        cases.value?.details as Array<IDetails>,
        currentCaseId,
        "origin"
      );
      await getNrrdAndJsonFileUrls(requests);
      originUrls.value = caseUrls.value as ICaseUrls;
    }

    if (!!originUrls.value?.nrrdUrls && originUrls.value?.nrrdUrls.length > 0) {
      allContrastUrls = originUrls.value.nrrdUrls;
      readyToLoad(allContrastUrls, "origin")?.then((data) => {
        emitter.emit("showRegBtnToRight", {
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
      emitter.emit("showRegBtnToRight", {
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
  state.switchCase = cases.value?.names[0] as string;

  gui
    .add(state, "switchCase", cases.value?.names as string[])
    .onChange(async (caseId) => {
      await onCaseSwitched(caseId);
      setUpGuiAfterLoading();
    });

  selectedContrastFolder = gui.addFolder("select display contrast");
}

function setUpGuiAfterLoading() {
  if (!!optsGui) {
    gui.removeFolder(optsGui);
    optsGui = undefined;
    state.showRegisterImages = true;
  }
  optsGui = gui.addFolder("opts");
  regCkeckbox = optsGui.add(state, "showRegisterImages");
  regCheckboxElement = regCkeckbox.domElement.childNodes[0] as HTMLInputElement;
  regCkeckbox.onChange(async () => {
    if (regCheckboxElement.disabled) {
      state.showRegisterImages = !state.showRegisterImages;
      return;
    }

    await onRegistedStateChanged(state.showRegisterImages);
  });
  optsGui.add(state, "release");
  optsGui.closed = false;
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

.nav_bar_left_container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.copper3d_sliceNumber {
  position: relative;
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
