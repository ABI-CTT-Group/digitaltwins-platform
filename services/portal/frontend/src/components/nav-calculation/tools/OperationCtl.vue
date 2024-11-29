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
    </v-container>
  </v-list-group>
</template>

<script setup lang="ts">
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

// Slider Controls


// Functional Buttons
const guiSettings = ref<any>();
let nrrdTools:Copper.NrrdTools;

type TTumourCenter = { center: { x: number; y: number; z: number; }};

const commFuncRadioValues = ref([
  { label: "Calculate Distance", value: "calculator", color: "calculator" },
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
    await getTumourWindowChrunk(casename as string);
  });

  emitter.on("finishloadcases", (val) => {
    guiSettings.value = val;
    commFuncRadiosDisabled.value = false;
    commFuncRadios.value = "calculator";
    toggleFuncRadios("calculator");
  });
  // xyz: 84 179 74
  emitter.on("loadcalculatortumour", (tool)=>{
    nrrdTools = tool as Copper.NrrdTools
  });
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
  }
  
  guiSettings.value.guiSetting[commFuncRadios.value].onChange();
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
