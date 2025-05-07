<template>
    <div ref="baseContainer" class="left-container dark guide-left-panel">
      <div v-show="showDebugPanel" ref="debugContainer" class="left_gui"></div>
      <div ref="canvasContainer" class="canvas_container"></div>
      <div v-show="showSliceIndex" ref="sliceIndexContainer" class="copper3d_sliceNumber">
          Tumour Segmentation Panel
      </div>

      <div v-show="enableUpload">
          <slot name="drag-to-upload"></slot>
      </div>

      <div v-show="showTumourDistancePanel">
          <slot name="tumour-distance-panel"></slot>
      </div>
    </div>
    <div
        v-show="showBottomNavBar"
        class="nav_bar_left_container"
        ref="bottomNavBarContainer"
    >
        <slot name="bottom-nav-bar"></slot>
    </div>
</template>

<script setup lang="ts">
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
import { GUI, GUIController } from "dat.gui";
import { ref, onMounted, onUnmounted, onBeforeUnmount, watch, watchEffect } from "vue";
// import emitter from "@/plugins/custom-emitter";
import loadingGif from "@/assets/loading.svg";
import {
  getEraserUrlsForOffLine,
  getCursorUrlsForOffLine,
} from "@/plugins/view-utils/tools";
import { switchAnimationStatus, addNameToLoadedMeshes } from "./leftCoreUtils";
import { ILoadedMeshes, } from "@/models/apiTypes";

let baseContainer = ref<HTMLDivElement>();
let debugContainer = ref<HTMLDivElement>();
let canvasContainer = ref<HTMLDivElement>();
let bottomNavBarContainer = ref<HTMLDivElement>();
let sliceIndexContainer = ref<HTMLDivElement>();

let gui = new GUI({ width: 300, autoPlace: false });

// Copper3D render scene core variables
let appRenderer: Copper.copperRenderer;
let nrrdTools: Copper.NrrdTools;
let scene: Copper.copperScene;
let loadBarMain = ref<Copper.loadingBarType>();
let loadingContainer = ref<HTMLDivElement>();
let progress = ref<HTMLDivElement>();   

// offline working variables
const eraserUrls = getEraserUrlsForOffLine();
const cursorUrls = getCursorUrlsForOffLine();

// trial variables
let toolNrrdStates: Copper.INrrdStates;

// core load images variables
let allSlices: Array<any> = [];
let allLoadedMeshes: Array<ILoadedMeshes> = [];

// used to trigger nrrdTools to display loaded images slices, once the filesCount === currentCaseContrastUrls.length
let filesCount = ref(0);
// when firstLoad is true, it means that we need to initialize the nrrdTools
let firstLoad = true;
// used to remove the nrrdTools.start function in scene preRenderCallbackFunction, when we unmount the component
let coreRenderId = 0;

const { currentCaseContrastUrls, currentCaseName, emitter } = defineProps({
    showSliceIndex:{
        type: Boolean,
        default: true
    },
    showDebugPanel:{
        type: Boolean,
        default: false
    },
    showTumourDistancePanel:{
        type: Boolean,
        default: false
    },
    showBottomNavBar:{
        type: Boolean,
        default: true
    },
    enableUpload:{
        type: Boolean,
        default: false
    },
    currentCaseContrastUrls:{
        type: Array<String>,
        default: []
    },
    currentCaseName:{
        type: String,
        default: ""
    },
    emitter:{
      type: Object,
    }
});

defineExpose({
    loadBarMain,
    loadingContainer,
    progress,
    gui,
    baseContainer
});

const loadMask = defineModel('loadMask', {
    type: Boolean,
    default: false
});

const emit = defineEmits(
  [
    "update:finishedCopperInit", 
    "update:getMaskData", 
    "update:sphereData", 
    "update:calculateSpherePositionsData", 
    "update:sliceNumber", 
    "update:afterLoadAllCaseImages", 
    "update:setMaskData", 
    "update:mouseDragContrast"]);

watch(() => currentCaseContrastUrls, (newVal, oldVal) => {

    if (newVal.length > 0) {
        readyToLoad(currentCaseName);
    }
});

onMounted(() => {
    initCopper();
});

function initCopper() {
    debugContainer.value?.appendChild(gui.domElement);

    appRenderer = new Copper.copperRenderer(
        baseContainer.value as HTMLDivElement,
        {
            guiOpen: false,
            alpha: true,
        }
    );

    nrrdTools = new Copper.NrrdTools(canvasContainer.value as HTMLDivElement);
    nrrdTools.setDisplaySliceIndexPanel(
        sliceIndexContainer.value as HTMLDivElement
    );
    // for offline working
    // nrrdTools.setBaseCanvasesSize(1.5);
    nrrdTools.setEraserUrls(eraserUrls);
    nrrdTools.setPencilIconUrls(cursorUrls);
    // nrrdTools.setMainAreaSize(3);

    // sphere plan b
    toolNrrdStates = nrrdTools.getNrrdToolsSettings();
    // toolsState.spherePlanB = false;

    loadBarMain.value = Copper.loading(loadingGif);

    loadingContainer.value = loadBarMain.value.loadingContainer;
    progress.value = loadBarMain.value.progress;

    (canvasContainer.value as HTMLDivElement).appendChild(
        loadBarMain.value.loadingContainer
    );

    setupCopperScene("nrrd_tools");
    appRenderer.animate();

    emit("update:finishedCopperInit", {
        appRenderer,
        nrrdTools,
        scene,
    });
}

function setupCopperScene(name: string) {
  scene = appRenderer!.getSceneByName(name) as Copper.copperScene;
  if (scene == undefined) {
    scene = appRenderer!.createScene(name) as Copper.copperScene;
    if (scene) {
      appRenderer!.setCurrentScene(scene);
    }
  }
}


// core load images

const readyToLoad = ( name: string) => {
  if (currentCaseContrastUrls.length > 0) {
    return new Promise<{ meshes: Array<Copper.nrrdMeshesType>; slices: any[] }>(
      (resolve, reject) => {
        loadAllNrrds(currentCaseContrastUrls as string[], name, resolve, reject);
      }
    );
  }
};

const loadAllNrrds = (
  urls: Array<string>,
  name: string,
  resolve?: (value: {
    meshes: Array<Copper.nrrdMeshesType>;
    slices: any[];
  }) => void,
  reject?: (reason?: any) => void
) => {
  switchAnimationStatus(loadingContainer.value!, progress.value!, "none");
  allSlices = [];
  allLoadedMeshes = [];
  for (let i = 0; i < urls.length; i++) {
    imageLoader(name, urls[i], i, urls.length, resolve);
  }
};

const imageLoader = (name:string, url:string, order: number, total:number, resolve?: (value: {
    meshes: Array<Copper.nrrdMeshesType>;
    slices: any[];
  }) => void) =>{
  const onload = ( volume: any, nrrdMesh: Copper.nrrdMeshesType, nrrdSlices: Copper.nrrdSliceType)=>{
    addNameToLoadedMeshes(nrrdMesh, name);
    const newNrrdSlice = Object.assign(nrrdSlices, { order });
    const newNrrdMesh = Object.assign(nrrdMesh, { order });
    allSlices.push(newNrrdSlice);
    allLoadedMeshes.push(newNrrdMesh);
    filesCount.value += 1;
    if (filesCount.value >= total) {
      allLoadedMeshes.sort((a: any, b: any) => {
        return a.order - b.order;
      });
      allSlices.sort((a: any, b: any) => {
        return a.order - b.order;
      });
      !!resolve && resolve({ meshes: allLoadedMeshes, slices: allSlices });
    }
  }
  scene?.loadNrrd(url, loadBarMain.value!, true, onload);
}

// hooks
const getContrastMove = (step:number, towards:"horizental"|"vertical") =>{
  emit("update:mouseDragContrast", { step, towards });
}
const getSliceNum = (index: number, contrastindex: number) => {
 emit("update:sliceNumber", { index, contrastindex });
};
const getMaskData = (
  image: ImageData,
  sliceId: number,
  label: string,
  width: number,
  height: number,
  clearAllFlag?: boolean) => {
  emit("update:getMaskData", {
    image,
    sliceId,
    label,
    width,
    height,
    clearAllFlag,
  }); 
};
const getSphereData = (sphereOrigin: number[], sphereRadius: number) => {
  emit("update:sphereData", {
    sphereOrigin,
    sphereRadius,
  });
};
const getCalculateSpherePositionsData = (tumourSphereOrigin:Copper.ICommXYZ | null, skinSphereOrigin:Copper.ICommXYZ | null, ribSphereOrigin:Copper.ICommXYZ | null, nippleSphereOrigin:Copper.ICommXYZ | null, aix:"x"|"y"|"z") => {
  emit("update:calculateSpherePositionsData", {
    tumourSphereOrigin,
    skinSphereOrigin,
    ribSphereOrigin,
    nippleSphereOrigin,
    aix
  });
};
const setMaskData = () => {
  emit("update:setMaskData");
};

// watch filesCount, when filesCount.value === currentCaseContrastUrls.length, then we can start to display the images
watch(filesCount, ()=>{
  if (
    filesCount.value != 0 &&
    filesCount.value === currentCaseContrastUrls.length
  ) {
    console.log("All files ready!");

    nrrdTools!.clear();
    nrrdTools!.setAllSlices(allSlices);

    if (firstLoad) {

      nrrdTools!.drag({ getSliceNum });
      nrrdTools!.draw({ getMaskData, getSphereData, getCalculateSpherePositionsData});
      nrrdTools!.setupGUI(gui as GUI);
      nrrdTools!.enableContrastDragEvents(getContrastMove)

      coreRenderId = scene?.addPreRenderCallbackFunction(nrrdTools!.start) as number;
      emitter!.emit("Core:NrrdTools", nrrdTools);
    } else {
      nrrdTools!.redrawMianPreOnDisplayCanvas();
    }

    if (loadMask.value) {
      setMaskData();
    }

    emit("update:afterLoadAllCaseImages", {
      allSlices,
      allLoadedMeshes,
    });

    firstLoad = false;
    loadMask.value = false;
  }
  setTimeout(() => {
    filesCount.value = 0;
  }, 1000);
})


onUnmounted(() => {
  scene?.removePreRenderCallbackFunction(coreRenderId);
});

</script>

<style>
.left-container {
  width: 100%;
  /* height: 100vh; */
  flex: 0 0 90%;
  overflow: hidden;
  position: relative;
  /* border: 1px solid palevioletred; */
}
/**
  * Hide the canvas element, because we use the nrrdTools to render the images
  make sure the canvas element is not visible and not affect the layout
  */
.left-container > canvas {
  height: 0 !important;
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
</style>