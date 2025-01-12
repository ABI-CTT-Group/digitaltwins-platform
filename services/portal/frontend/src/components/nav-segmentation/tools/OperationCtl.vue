<template>
    <Operation>
      <template #Calculator>
        <Calculator />
      </template>

      <template #FunctionalControl>
        <FunctionalControl
          v-model="commFuncRadios"
          :disabled="commFuncRadiosDisabled"
          :radio-values="commFuncRadioValues"
          @update:selected-radio="toggleFuncRadios" 
          />
      </template>

      <template #SliderControl>
        <SliderControl 
          v-model:slider-radio="commSliderRadios"
          v-model:slider="slider"
          :disabled="commSliderRadiosDisabled"
          :slider-radio-values="commSliderRadioValues"
          :slider-color="sliderColor"
          :slider-disabled="sliderDisabled"
          :slider-max="sliderMax"
          :slider-min="sliderMin"
          :slider-step="sliderStep"
          @update:selected-slider-radio="toggleSliderRadios"
          @update:slider="toggleSlider"
          @update:slider-finished="toggleSliderFinished"
        />
      </template>

      <template #ButtonControl>
        <ButtonsControl
          :comm-func-btn-values="commFuncBtnValues"
          @update:btnClicked="onBtnClick"
        />
      </template>

      <template #OperationAdvance>
        <OperationAdvance />
      </template>
    </Operation>
</template>

<script setup lang="ts">
import OperationAdvance from "./advance/OperationAdvance.vue";
import Calculator from "./advance/Calculator.vue";
import Operation from "@/components/nav-components/Operation.vue"
import FunctionalControl from "@/components/nav-components/functionalCtl/FunctionalControl.vue";
import SliderControl from "@/components/nav-components/sliderCtl/SliderControl.vue";
import ButtonsControl from "@/components/nav-components/buttonCtl/ButtonsControl.vue";
import { ref, onMounted } from "vue";
import { storeToRefs } from "pinia";
import emitter from "@/plugins/bus";
import * as Copper from "copper3d";
import {
  useTumourWindowStore
} from "@/store/app";
import { setTumourPosition } from "@/components/utils";

// load tumour window
const { tumourWindow } = storeToRefs(useTumourWindowStore());
const { getTumourWindowChrunk } = useTumourWindowStore();

// Functional Controls
const commFuncRadios = ref("segmentation");
const commFuncRadiosDisabled = ref(true);
const prebtn = ref("segmentation")

// Slider Controls
const commSliderRadios = ref("");
const commSliderRadiosDisabled = ref(true);
const slider = ref(0);
const sliderColor = ref("grey");
const sliderDisabled = ref(true);
const sliderMax = ref(100);
const sliderMin = ref(0);
const sliderStep = ref(1);

// Functional Buttons
const btnUndoDisabled = ref(true);
const btnResetZoomDisabled = ref(true);
const btnClearDisabled = ref(true);
const btnClearAllDisabled = ref(true);

const contrastDragSensitivity = ref(25);

const guiSettings = ref<any>();
let nrrdTools:Copper.NrrdTools;

type TTumourCenter = { center: { x: number; y: number; z: number; }};

const commFuncRadioValues = ref([
  { label: "Pencil", value: "segmentation", color: "success" },
  { label: "Sphere", value: "sphere", color: "warning" },
  { label: "Eraser", value: "Eraser", color: "error" },
  { label: "Brush", value: "brush", color: "info" },
  { label: "Calculate Distance", value: "calculator", color: "calculator" },
]);

const commSliderRadioValues = ref([
  { label: "Opacity", value: "globalAlpha", color: "success" },
  { label: "B&E Size", value: "brushAndEraserSize", color: "info" },
  { label: "WindowHigh", value: "windowHigh", color: "warning" },
  { label: "WindowCenter", value: "windowLow", color: "error" },
  { label: "WindowSensitivity", value: "sensitivity", color: "pink-darken-1" },
]);

const commFuncBtnValues = ref([
  {
    label: "Undo",
    value: "undo",
    disabled: btnUndoDisabled,
    color: "nav-success-2",
  },
  {
    label: "Reset Zoom",
    value: "resetZoom",
    disabled: btnResetZoomDisabled,
    color: "nav-success-2",
  },
  {
    label: "Clear Slice Mask",
    value: "clear",
    disabled: btnClearDisabled,
    color: "nav-success-2",
  },
  {
    label: "Clear All Slices Masks",
    value: "clearAll",
    disabled: btnClearAllDisabled,
    color: "nav-success",
  },
]);

onMounted(() => {
  manageEmitters();
});

function manageEmitters() {

  emitter.on("caseswitched", async (casename)=>{
    try{
      setTimeout(()=>{
        commFuncRadios.value = "segmentation"
      },500)
    }catch(e){
      console.log("first time load images -- ignore");
    }
    commFuncRadiosDisabled.value = true;
    commSliderRadiosDisabled.value = true;
    sliderDisabled.value = true;

    btnUndoDisabled.value = true;
    btnResetZoomDisabled.value = true;
    btnClearDisabled.value = true;
    btnClearAllDisabled.value = true;
    await getTumourWindowChrunk(casename as string);
  });

  emitter.on("finishloadcases", (val) => {
    guiSettings.value = val;
    commSliderRadios.value = "globalAlpha";
    updateSliderSettings();
    commFuncRadiosDisabled.value = false;
    commSliderRadiosDisabled.value = false;
    sliderDisabled.value = false;

    btnUndoDisabled.value = false;
    btnResetZoomDisabled.value = false;
    btnClearDisabled.value = false;
    btnClearAllDisabled.value = false;
  });

  emitter.on("dragImageWindowCenter", (step)=>{
    dragToChangeImageWindow("windowLow", step as number);
  })
  emitter.on("dragImageWindowHigh", (step)=>{
    dragToChangeImageWindow("windowHigh", step as number);
  })
  // xyz: 84 179 74
  emitter.on("loadcalculatortumour", (tool)=>{
    nrrdTools = tool as Copper.NrrdTools
  });
}

function dragToChangeImageWindow(type:"windowHigh"|"windowLow", step:number){
  let val = 0;
  if (type==="windowHigh"){
    val = guiSettings.value.guiSetting[type].value.windowHigh + step * contrastDragSensitivity.value;
  }else{
    val = guiSettings.value.guiSetting[type].value.windowLow + step * contrastDragSensitivity.value;
  }
  
  if(val >=guiSettings.value.guiSetting[type].max || val<=0){
    return
  }

  guiSettings.value.guiSetting[type].onChange(val);
 
}

function setupTumourSpherePosition(){

  if (!!tumourWindow.value){
    // Note: the tumour center we recieve is in mm, we need to convert it to (pixel, pixel, mm) in Axial view
    // pixel / spacing = mm
    // mm * spacing = pixel
    setTumourPosition(nrrdTools, (tumourWindow.value as TTumourCenter).center)
  }
}

function toggleFuncRadios(val: any) {

  if(val === "calculator"){
    emitter.emit("open_calculate_box", "Calculator")
    guiSettings.value.guiState["calculator"] = true;
    guiSettings.value.guiState["sphere"] = false;
    setupTumourSpherePosition()
    emitter.emit("calculator timer", "start");
  }else{
    emitter.emit("close_calculate_box", "Calculator")
    guiSettings.value.guiState["calculator"] = false;
    if (val === "sphere") {
      guiSettings.value.guiState["sphere"] = true;
    } else {
      guiSettings.value.guiState["sphere"] = false;
      if (val === "Eraser") {
        guiSettings.value.guiState["Eraser"] = true;
      } else {
        guiSettings.value.guiState["Eraser"] = false;
        if (val === "segmentation") {
          guiSettings.value.guiState["segmentation"] = true;
        } else {
          guiSettings.value.guiState["segmentation"] = false;
          guiSettings.value.guiSetting["segmentation"].onChange();
          return;
        }
      }
    }
  }
  

  if(prebtn.value==="sphere" && prebtn!==val){
    guiSettings.value.guiSetting["sphere"].onChange();
  }
  if(prebtn.value==="calculator" && prebtn!==val){
    guiSettings.value.guiSetting["calculator"].onChange();
  }

  prebtn.value=val;  
  guiSettings.value.guiSetting[commFuncRadios.value].onChange();
}

function toggleSliderRadios(val: any) {
  updateSliderSettings();
}

function toggleSlider(val: number) {

  if(commSliderRadios.value === "sensitivity"){
    contrastDragSensitivity.value = val;
    return;
  }

  if (commSliderRadios.value !== "windowHigh" && commSliderRadios.value !== "windowLow") {
    guiSettings.value.guiState[commSliderRadios.value] = val;
  }
  if (commSliderRadios.value === "brushAndEraserSize") {
    guiSettings.value.guiSetting[commSliderRadios.value].onChange();
  }
  if (commSliderRadios.value === "windowHigh" || commSliderRadios.value === "windowLow") {
    guiSettings.value.guiSetting[commSliderRadios.value].onChange(val);
  }
}

function toggleSliderFinished(val: number) {
  if (commSliderRadios.value === "windowHigh" || commSliderRadios.value === "windowLow") {
    guiSettings.value.guiSetting[commSliderRadios.value].onFinished();
  }
}

function updateSliderSettings() {

  const radioSettings = commSliderRadioValues.value.filter(
    (item) => item.value === commSliderRadios.value
  );

  if (radioSettings.length > 0) {
    sliderColor.value = radioSettings[0].color;
  }

  if(commSliderRadios.value === "sensitivity"){
    sliderMax.value = 50;
    sliderMin.value = 1;
    sliderStep.value = 1;
    slider.value = contrastDragSensitivity.value;
    return;
  }

  if (commSliderRadios.value === "windowHigh"){
    slider.value = guiSettings.value.guiSetting[commSliderRadios.value].value.windowHigh;
  }else if (commSliderRadios.value === "windowLow"){
    slider.value =
    guiSettings.value.guiSetting[commSliderRadios.value].value.windowLow;
  }else{
    slider.value = guiSettings.value.guiState[commSliderRadios.value];
  }
    
  sliderMax.value = guiSettings.value.guiSetting[commSliderRadios.value].max;
  sliderMin.value = guiSettings.value.guiSetting[commSliderRadios.value].min;
  sliderStep.value = guiSettings.value.guiSetting[commSliderRadios.value].step;
}

function onBtnClick(val: any) {
  guiSettings.value.guiState[val].call();
}

</script>

