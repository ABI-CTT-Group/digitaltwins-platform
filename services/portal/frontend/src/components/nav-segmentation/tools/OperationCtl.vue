<template>
  <v-list-group value="Operation" class="guide-operation-overall" data-tool="operationtool">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="nav-success"
        prepend-icon="mdi-axe"
        title="Operation Settings"
      ></v-list-item>
    </template>
    <!-- Functional Control -->
    <Calculator />
    <v-container fluid>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <v-radio-group
        class="radio-group guide-operation-functional-control"
        v-model="commFuncRadios"
        label="Functional Controller"
        :inline="true"
        :disabled="commFuncRadiosDisabled"
        @update:modelValue="toggleFuncRadios"
      >
        <v-radio
          v-for="(item, idx) in commFuncRadioValues"
          :key="idx"
          :label="item.label"
          :value="item.value"
          :color="item.color"
        ></v-radio>
      </v-radio-group>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <!-- </v-container> -->

      <!-- Slider Controls -->
      <!-- <v-container fluid> -->
      <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <v-radio-group
        class="radio-group guide-operation-slider-control"
        v-model="commSliderRadios"
        label="Slider Controller"
        :inline="true"
        :disabled="commSliderRadiosDisabled"
        @update:modelValue="toggleSliderRadios"
      >
        <v-radio
          v-for="(item, idx) in commSliderRadioValues"
          :key="idx"
          :label="item.label"
          :value="item.value"
          :color="item.color"
        ></v-radio>
      </v-radio-group>
      <v-slider
        v-model="slider"
        :color="sliderColor"
        thumb-label="always"
        :disabled="sliderDisabled"
        :max="sliderMax"
        :min="sliderMin"
        :step="sliderStep"
        @update:modelValue="toggleSlider"
        @end="toggleSliderFinished"
      ></v-slider>
      <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
      ></v-progress-linear>

      <!-- Buttons -->
      <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
      ></v-progress-linear>

      <div class="guide-operation-comm-btns">
          <v-btn
          v-for="(btn, idx) in commFuncBtnValues"
          block
          density="comfortable"
          variant="outlined"
          class="my-1"
          :key="idx"
          :color="btn.color"
          :disabled="btn.disabled"
          @click="onBtnClick(btn.value)"
          >{{ btn.label }}</v-btn
        >
      </div>
      
      <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
      ></v-progress-linear>
    </v-container>
    <OperationAdvance />
    
  </v-list-group>
</template>

<script setup lang="ts">
import OperationAdvance from "./advance/OperationAdvance.vue";
import Calculator from "./advance/Calculator.vue";
import { ref, onMounted } from "vue";
import { storeToRefs } from "pinia";
import emitter from "@/plugins/bus";
import * as Copper from "@/ts/index";
import {
  useTumourWindowStore
} from "@/store/app";
// import * as Copper from "copper3d";

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
    nrrdTools.setCalculateDistanceSphere((tumourWindow.value as TTumourCenter).center.x, (tumourWindow.value as TTumourCenter).center.y, (tumourWindow.value as TTumourCenter).center.z, "tumour");
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

<style>
.v-selection-control-group--inline {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0 10px;
}
</style>
