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
import { ref, onMounted, onUnmounted, onBeforeUnmount } from "vue";
import emitter from "@/plugins/custom-emitter";
import loadingGif from "@/assets/loading.svg";
import {
  findCurrentCase,
  revokeAppUrls,
  revokeRegisterNrrdImages,
  getEraserUrlsForOffLine,
  getCursorUrlsForOffLine,
} from "@/plugins/view-utils/tools";

let baseContainer = ref<HTMLDivElement>();
let debugContainer = ref<HTMLDivElement>();
let canvasContainer = ref<HTMLDivElement>();
let bottomNavBarContainer = ref<HTMLDivElement>();
let sliceIndexContainer = ref<HTMLDivElement>();

let gui = new GUI({ width: 300, autoPlace: false });

// Copper3D render scene core variables
let appRenderer = ref<Copper.copperRenderer>();
let nrrdTools = ref<Copper.NrrdTools>();
let scene = ref<Copper.copperScene>();
let loadBarMain = ref<Copper.loadingBarType>();
let loadingContainer = ref<HTMLDivElement>();
let progress = ref<HTMLDivElement>();   

// offline working variables
const eraserUrls = getEraserUrlsForOffLine();
const cursorUrls = getCursorUrlsForOffLine();

// trial variables
let toolNrrdStates: Copper.INrrdStates;

defineProps({
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
    }
})

defineExpose({
    appRenderer,
    nrrdTools,
    scene,
    loadBarMain,
    loadingContainer,
    progress,
    gui,
    baseContainer
})


onMounted(() => {
    initCopper();
});

function initCopper() {
    debugContainer.value?.appendChild(gui.domElement);

    appRenderer.value = new Copper.copperRenderer(
        baseContainer.value as HTMLDivElement,
        {
            guiOpen: false,
            alpha: true,
        }
    );

    nrrdTools.value = new Copper.NrrdTools(canvasContainer.value as HTMLDivElement);

    emitter.emit("Core:NrrdTools", nrrdTools.value);

    nrrdTools.value.setDisplaySliceIndexPanel(
        sliceIndexContainer.value as HTMLDivElement
    );
    // for offline working

    // nrrdTools.setBaseCanvasesSize(1.5);
    nrrdTools.value.setEraserUrls(eraserUrls);
    nrrdTools.value.setPencilIconUrls(cursorUrls);
    // nrrdTools.setMainAreaSize(3);

    // sphere plan b
    toolNrrdStates = nrrdTools.value.getNrrdToolsSettings();
    // toolsState.spherePlanB = false;

    loadBarMain.value = Copper.loading(loadingGif);

    loadingContainer.value = loadBarMain.value.loadingContainer;
    progress.value = loadBarMain.value.progress;

    (canvasContainer.value as HTMLDivElement).appendChild(
        loadBarMain.value.loadingContainer
    );

    // setupGui();
    setupCopperScene("nrrd_tools");
    appRenderer.value.animate();
}

function setupCopperScene(name: string) {
  scene.value = appRenderer.value!.getSceneByName(name) as Copper.copperScene;
  if (scene.value == undefined) {
    scene.value = appRenderer.value!.createScene(name) as Copper.copperScene;
    if (scene) {
      appRenderer.value!.setCurrentScene(scene.value);
    }
  }
}


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