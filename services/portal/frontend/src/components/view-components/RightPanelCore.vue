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
  "update:finishedCopperInit",
  "update:resetNrrdImageView",
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

// for nrrd loader
let nrrdOrigin: number[] = [];
let nrrdSpacing: number[] = [];
let nrrdBias: THREE.Vector3;
let correctedOrigin: number[] = [];
/**
 * pixel / spacing = mm
 * mm * spacing = pixel
 */
let nrrdRASDimensions: number[] = []; // mm
let nrrdDimensions: number[] = []; // pixels


// for deal with single/double click on a div
let clickCount = 0;
let clickTimer: any = null;
let validFlag = false;

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

    emit("update:finishedCopperInit", { appRenderer, copperScene, panelOperator, copperLoadingAnimationForNrrdLoader});
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

/**
 * load the nrrd case, calculate the nrrd image origin, spacing, ras, dimensions, bias for load nipple, breast model
 * get the nrrd meshes and slices
 * @param nrrdUrl nrrd case url
 */
 function loadNrrd(nrrdUrl: string, imageType: "register" | "origin") {
  
  if (copperScene === undefined) {
    console.log("copperScene is missing!");
    return;
  }
  // remove GUI
  const opts: Copper.optsType = {
    openGui: false,
    // container: baseContainer_gui.value,
  };
  return new Promise<{ origin: number[], 
                      correctedOrigin:number[], 
                      spacing: number[],  
                      ras: number[], 
                      dimensions:number[], 
                      bias: THREE.Vector3,  
                      nrrdMesh:Copper.nrrdMeshesType, 
                      nrrdSlices:Copper.nrrdSliceType}>((resolve, reject) => {
    const nrrdCallback = async (
    volume: any,
    nrrdMesh: Copper.nrrdMeshesType,
    nrrdSlices: Copper.nrrdSliceType,
  ) => {
    // adjust nrrd volume contrast windowHigh and windowLow
    // volume.windowHigh = 2000;
    // volume.windowLow = 82;
    // volume.repaintAllSlices();

    nrrdOrigin = volume.header.space_origin.map((num: any) => Number(num));
    nrrdSpacing = volume.spacing;
    nrrdRASDimensions = volume.RASDimensions; // mm
    nrrdDimensions = volume.dimensions; // pixels

    const x_bias = -(nrrdOrigin[0] * 2 + nrrdRASDimensions[0]) / 2;
    const y_bias = -(nrrdOrigin[1] * 2 + nrrdRASDimensions[1]) / 2;
    const z_bias = -(nrrdOrigin[2] * 2 + nrrdRASDimensions[2]) / 2;

    nrrdBias = new THREE.Vector3(x_bias, y_bias, z_bias);
    correctedOrigin = [
          nrrdOrigin[0] + x_bias,
          nrrdOrigin[1] + y_bias,
          nrrdOrigin[2] + z_bias,
        ];  

    nrrdMesh.x.name = imageType + "_Sagittal";
    nrrdMesh.y.name = imageType + "_Cornal";
    nrrdMesh.z.name = imageType + "_Axial";
    
    !!resolve && resolve({ origin: nrrdOrigin, correctedOrigin, spacing: nrrdSpacing,  ras: nrrdRASDimensions, dimensions:nrrdDimensions, bias: nrrdBias, nrrdMesh, nrrdSlices});
    
  };

  (copperScene as Copper.copperScene).loadNrrd(
    nrrdUrl,
    copperLoadingAnimationForNrrdLoader!,
    true,
    nrrdCallback,
    opts
  );
  })
}

function onNavBarSingleClick(view: string, loadNrrdMeshes: Copper.nrrdMeshesType, loadNrrdSlices: Copper.nrrdSliceType) {
  panelOperator.start();
  copperScene.controls.mouseButtons.LEFT = -1;
  clickCount++;
  if (clickCount === 1) {
    clickTimer = setTimeout(() => {
      switch (view) {
        case "sagittal":
          loadNrrdMeshes.x.visible = true;
          loadNrrdMeshes.y.visible = false;
          loadNrrdMeshes.z.visible = false;
          panelOperator.setSlicePrams(loadNrrdSlices.x);
          break;
        case "axial":
          loadNrrdMeshes.x.visible = false;
          loadNrrdMeshes.y.visible = false;
          loadNrrdMeshes.z.visible = true;
          panelOperator.setSlicePrams(loadNrrdSlices.z);
          break;
        case "coronal":
          loadNrrdMeshes.x.visible = false;
          loadNrrdMeshes.y.visible = true;
          loadNrrdMeshes.z.visible = false;
          panelOperator.setSlicePrams(loadNrrdSlices.y);
          break;
        case "clock":
          validFlag = !validFlag;
          // valideClock(
          //   validFlag,
          //   copperScene,
          //   baseContainer.value as HTMLElement,
          //   nippleTl,
          //   nippleTr,
          //   loadNrrdMeshes
          // );
          break;
        case "3dview":
          backTo3DView(loadNrrdMeshes)
          break;
        case "reset":
          resetNrrdImageView(loadNrrdMeshes);
          break;
      }
      clickCount = 0;
    }, 200);
  }
}

function onNavBarDoubleClick(view: string, loadNrrdMeshes: Copper.nrrdMeshesType, loadNrrdSlices: Copper.nrrdSliceType) {
  if(view == "reset" || view == "3dview") return;
  
  !!clickTimer && clearTimeout(clickTimer);
  clickCount = 0;
  copperScene.controls.mouseButtons.LEFT = -1;
  copperScene.controls.reset();
  switch (view) {
    case "sagittal":
      loadNrrdMeshes.x.visible = true;
      loadNrrdMeshes.y.visible = false;
      loadNrrdMeshes.z.visible = false;
      panelOperator.setSlicePrams(loadNrrdSlices.x);
      copperScene.loadViewUrl("/nrrd_view_sagittal.json");
      break;

    case "axial":
      loadNrrdMeshes.x.visible = false;
      loadNrrdMeshes.y.visible = false;
      loadNrrdMeshes.z.visible = true;
      panelOperator.setSlicePrams(loadNrrdSlices.z);
      copperScene.loadViewUrl("/nrrd_view.json");
      break;

    case "coronal":
      loadNrrdMeshes.x.visible = false;
      loadNrrdMeshes.y.visible = true;
      loadNrrdMeshes.z.visible = false;
      panelOperator.setSlicePrams(loadNrrdSlices.y);
      copperScene.loadViewUrl("/nrrd_view_coronal.json");
      break;
  }
}

const backTo3DView = (loadNrrdMeshes: Copper.nrrdMeshesType)=>{
  panelOperator.dispose();
  loadNrrdMeshes.x.visible = true;
  loadNrrdMeshes.y.visible = true;
  loadNrrdMeshes.z.visible = true;
  // valideClock(false, copperScene, baseContainer.value as HTMLElement);
  copperScene.controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
}

const resetNrrdImageView = (loadNrrdMeshes: Copper.nrrdMeshesType) => {
  copperScene.loadViewUrl("/nrrd_view.json");
  copperScene.controls.reset();
  backTo3DView(loadNrrdMeshes);
  emit("update:resetNrrdImageView", { loadNrrdMeshes });
};

function removeOldMeshes(meshSet: THREE.Object3D[]) {
  if (!!copperScene) {
    (copperScene as Copper.copperScene).scene.remove(...meshSet);
    meshSet.forEach((element) => {
      element.traverse((case_mesh) => {
        if ((case_mesh as THREE.Mesh).isMesh) {
          (case_mesh as THREE.Mesh).geometry.dispose();
        }
      });
    });
    meshSet.length = 0;
  }
} 

defineExpose({
  baseContainer,
  guiContainer,
  loadingContainer, 
  progress,
  copperLoadingAnimationForNrrdLoader,
  loadNrrd,
  removeOldMeshes,
  onNavBarSingleClick,
  onNavBarDoubleClick,
  backTo3DView,
  resetNrrdImageView
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