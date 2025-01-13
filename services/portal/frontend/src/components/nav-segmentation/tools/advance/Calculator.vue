<template>
  <v-list-group value="Calculator">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="nav-success-2"
        prepend-icon="mdi-map-marker-distance"
        title="Calculate Distance"
      ></v-list-item>
    </template>
    <v-container fluid>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <v-radio-group
        class="radio-group"
        v-model="calculatorPickerRadios"
        label=""
        :inline="true"
        :disabled="calculatorPickerRadiosDisabled"
        @update:modelValue="toggleCalculatorPickerRadios"
      >
        <v-radio
          v-for="(item, idx) in commFuncRadioValues"
          :key="idx"
          :label="item.label"
          :value="item.value"
          :color="item.color"
        ></v-radio>
      </v-radio-group>
      <v-btn
      block
      density="comfortable"
      :disabled="calculatorPickerRadiosDisabled"
      @click="onBtnClick('finish')"
      >Finish</v-btn>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
    </v-container>
  </v-list-group>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import emitter from "@/plugins/custom-emitter";
import * as Copper from "copper3d";

// buttons
const calculatorPickerRadios = ref("tumour");
const calculatorPickerRadiosDisabled = ref(true);

const commFuncRadioValues = ref([
  // { label: "Tumour", value: "tumour", color: "#4CAF50" },
  { label: "Skin", value: "skin", color: "#FFEB3B" },
  { label: "Nipple", value: "nipple", color: "#E91E63" },
  { label: "Ribcage", value: "ribcage", color: "#2196F3" },
]);

const guiSettings = ref<any>();
const startTime = ref<number[]>([0,0,0]);
const skinTime = ref<string>();
const nippleTime = ref<string>();
const ribTime = ref<string>();
const finishTime = ref<string>();
  


onMounted(() => {
  manageEmitters();
});

function manageEmitters() {
  emitter.on("Segementation:CaseSwitched", emitterOnCaseSwitched);
  emitter.on("Segmentation:FinishLoadAllCaseImages", emitterOnFinishLoadAllCaseImages);
  emitter.on("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox);
  emitter.on("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox);
  emitter.on("SegmentationTrial:CalulatorTimerFunction", emitterOnCalulatorTimerFunction);
}

const emitterOnCaseSwitched = ()=>{
  if (!!guiSettings.value && guiSettings.value.guiState["calculator"]) onBtnClick("load case");
  emitter.emit("Common:CloseCalculatorBox", "Calculator");
}
const emitterOnFinishLoadAllCaseImages = (val:
  {
    guiState: Copper.IGUIStates;
    guiSetting: Copper.IGuiParameterSettings;
  }
) => {
  guiSettings.value = val;
  calculatorPickerRadios.value = "tumour";
  if(!!guiSettings.value && guiSettings.value.guiState["calculator"]) calculatorPickerRadiosDisabled.value = false;
}
const emitterOnOpenCalculatorBox = ()=>{
  calculatorPickerRadiosDisabled.value = false;      
}
const emitterOnCloseCalculatorBox = ()=>{
  calculatorPickerRadiosDisabled.value = true;
  onBtnClick("close calculate")
}
const emitterOnCalulatorTimerFunction = (status: string)=>{
  calculatorTimerReport(status);
}

function calculatorTimerReport(status:string){

  const now = new Date();
  const currentTime = [now.getHours(), now.getMinutes(), now.getSeconds()]
  switch (status) {
      case "start":
        console.log("start timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
        startTime.value = currentTime;
        nippleTime.value = "";
        skinTime.value = "";
        ribTime.value = "";
        finishTime.value = "";
        break;
      case "skin":
        console.log("skin timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
        break;
      case "nipple":
        console.log("nipple timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
        break;
      case "ribcage":
        console.log("ribcage timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
        break;
      case "finish":
        console.log("finish timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
        break;
    
      default:
        break;
    }
}

function toggleCalculatorPickerRadios(val: string | null) {
  if (val === "skin"){
    // "tumour" | "skin" | "nipple" | "ribcage"
    guiSettings.value.guiState["cal_distance"] = "skin";
  }
  if (val === "nipple"){
    guiSettings.value.guiState["cal_distance"] = "nipple";
  }
  if (val === "ribcage"){
    guiSettings.value.guiState["cal_distance"] = "ribcage";
  }

  guiSettings.value.guiSetting["cal_distance"].onChange(calculatorPickerRadios.value);
  
}

function onBtnClick(val:string){
  if (!!guiSettings.value){
    calculatorPickerRadios.value = "tumour";
    guiSettings.value.guiState["cal_distance"] = "tumour";
    calculatorPickerRadiosDisabled.value = true;

    calculatorTimerReport("finish")
  }
}

onUnmounted(() => {
  emitter.off("Segementation:CaseSwitched", emitterOnCaseSwitched);
  emitter.off("Segmentation:FinishLoadAllCaseImages", emitterOnFinishLoadAllCaseImages);
  emitter.off("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox);
  emitter.off("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox);
  emitter.off("SegmentationTrial:CalulatorTimerFunction", emitterOnCalulatorTimerFunction);
})

</script>

<style scoped></style>
  