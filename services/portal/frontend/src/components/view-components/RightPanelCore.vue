<template>
    <div ref="baseContainer" class="right_container guide-right-panel">
        <div v-show="showLoadingAnimation" ref="panelLoadingContainer" class="loading">
            <div class="loading_text text-cyan-darken-3">Load tumour model...</div>
        </div>
        <slot name="tumour-distance-panel"></slot>
        <div v-show="showGuiPanel" ref="guiContainer" class="right_gui"></div>
    </div>
    <div v-show="showBottomNavBar" class="nav_bar_right_container" ref="nav_bar_right_container">
        <slot name="bottom-nav-bar"></slot>
    </div>
</template>

<script setup lang="ts">
import * as THREE from "three";
import * as Copper from "copper3d";
import "copper3d/dist/css/style.css";
import { ref, onMounted } from 'vue'
import loadingGif from "@/assets/loading.svg";
import { PanelOperationManager, valideClock, deepClone, processPointsCloud } from "@/plugins/view-utils/utils-right";
defineProps({
    showBottomNavBar:{
        type: Boolean,
        default: true
    },
    showGuiPanel: {
        type: Boolean,
        default: false
    },
    showLoadingAnimation: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits([
  "finishedCopperInit"
])

let baseContainer = ref<HTMLDivElement>();
let guiContainer = ref<HTMLDivElement>();
let panelLoadingContainer = ref<HTMLDivElement>();
let loadingContainer = ref<HTMLDivElement>();
let progress = ref<HTMLDivElement>();
let copperLoadingAnimationContainer: Copper.loadingBarType = Copper.loading(loadingGif);
let copperLoadingAnimationForNrrdLoader: Copper.loadingBarType = Copper.loading(loadingGif);

let appRenderer: Copper.copperRenderer;
let copperScene: Copper.copperScene;
let panelOperator: PanelOperationManager;

onMounted(() => {
    initCopper();
})

function initCopper() {
    panelLoadingContainer.value!.appendChild(copperLoadingAnimationContainer.loadingContainer);
    loadingContainer.value = copperLoadingAnimationContainer.loadingContainer;
    progress.value = copperLoadingAnimationContainer.progress;

    appRenderer = new Copper.copperRenderer(baseContainer.value as HTMLDivElement, {
      guiOpen: false,
      alpha: true,
      logarithmicDepthBuffer: true,
    });

    appRenderer.renderer.domElement.style.position = "fixed"
    // appRenderer.renderer.sortObjects = false;

    copperLoadingAnimationForNrrdLoader = Copper.loading(loadingGif);

    // appRenderer.container.appendChild(loadBar1.loadingContainer);

    initScene("display_nrrd");
    initPanelOperator();
    appRenderer.animate();

    emit("finishedCopperInit", { appRenderer, copperScene, panelOperator, copperLoadingAnimationForNrrdLoader});
}

function initPanelOperator() {
   panelOperator = new PanelOperationManager(baseContainer.value as HTMLDivElement);
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



defineExpose({
    baseContainer,
    guiContainer,
    loadingContainer, 
    progress,
    copperLoadingAnimationForNrrdLoader
})

</script>

<style scoped>
.right_container {
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