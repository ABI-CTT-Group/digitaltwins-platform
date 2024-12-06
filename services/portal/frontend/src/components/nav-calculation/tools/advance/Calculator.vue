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
          @update:modelValue="toggleCalculatorPickerRadios"
        >
          <v-radio
            v-for="(item, idx) in commFuncRadioValues"
            :key="idx"
            :label="item.label"
            :value="item.value"
            :color="item.color"
            :disabled="item.disabled"
          ></v-radio>
        </v-radio-group>

        <v-select
          class="mx-4"
          :items="clockFace"
          v-model="selectedClockFace"
          density="comfortable"
          label="Clock Face"
          variant="outlined"
          :disabled="clockFaceDisabled"
          @update:modelValue="onClockFaceChange"
        ></v-select>
        <v-btn
          class="ma-1"
          block
          density="comfortable"
          :disabled="finishBtnDisabled"
          @click="onBtnClick('finish')"
        >Finish</v-btn>
        <v-btn
          v-if="showBtn"
          color="pink"
          class="ma-1"
          block
          density="comfortable"
          @click="onNextCaseClick()"
        >Next Case</v-btn>
        <v-progress-linear
          color="nav-success-2"
          buffer-value="0"
          stream
        ></v-progress-linear>
      </v-container>
    </v-list-group>
  </template>
  
  <script setup lang="ts">
  import { ref, onMounted } from "vue";
  import * as Copper from "@/ts/index";
  import emitter from "@/plugins/custom-emitter";
  import { ITumourStudyAppDetail } from "@/models/apiTypes";
  
  // buttons
  const calculatorPickerRadios = ref("tumour");
  const finishBtnDisabled = ref(true);
  const showBtn = ref(false);
  const clockFaceDisabled = ref(true);
  const clockFace = ref(["12:00", "1:00", "2:00", "3:00", "4:00", "5:00", "6:00", "7:00", "8:00", "9:00", "10:00", "11:00", "central"]);
  const selectedClockFace = ref("");
  
  const commFuncRadioValues = ref([
    // { label: "Tumour", value: "tumour", color: "#4CAF50" },
    { label: "Skin", value: "skin", color: "#FFEB3B", disabled: false },
    { label: "Nipple", value: "nipple", color: "#E91E63", disabled: true },
    { label: "Ribcage", value: "ribcage", color: "#2196F3", disabled: true },
  ]);
  
  const guiSettings = ref<any>();
  const startTime = ref<number[]>([0,0,0]);
  const skinTime = ref<string>();
  const nippleTime = ref<string>();
  const ribTime = ref<string>();
  const finishTime = ref<string>();
  let nrrdTools:Copper.NrrdTools;
  let workingCase: ITumourStudyAppDetail;
  const now = new Date();
    

  
  onMounted(() => {
    manageEmitters();
  });
  
  function manageEmitters() {
    emitter.on("TumourStudy:ImageLoaded", (study: ITumourStudyAppDetail) => {
      console.log("TumourStudy:ImageLoaded", study);
      selectedClockFace.value = "";
      commFuncRadioValues.value[0].disabled = false;
      workingCase = study;
      calculatorPickerRadios.value = "tumour";
      setupTumourSpherePosition()
    });
  
    emitter.on("TumourStudy:Status", (status: string)=>{
      calculatorTimerReport(status);
    })

    // First time init Calculator
    emitter.on("TumourStudy:NrrdTools", (tool: Copper.NrrdTools)=>{
      nrrdTools = tool
      guiSettings.value = nrrdTools.getGuiSettings()
      guiSettings.value.guiState["calculator"] = true;
      guiSettings.value.guiState["sphere"] = false;
      guiSettings.value.guiSetting["calculator"].onChange();
    });
  }

  
function setupTumourSpherePosition(){

  const tumourCenter = workingCase.tumour_position.center;
  nrrdTools.setCalculateDistanceSphere(tumourCenter.x, tumourCenter.y, tumourCenter.z, "tumour");
}


  function calculatorTimerReport(status:string){

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
          commFuncRadioValues.value[1].disabled = false;
          console.log("skin timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
          break;
        case "nipple":
          commFuncRadioValues.value[2].disabled = false;
          console.log("nipple timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
          break;
        case "ribcage":
          clockFaceDisabled.value = false;
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
      calculatorTimerReport("start");
      guiSettings.value.guiState["cal_distance"] = "skin";
    }
    if (val === "nipple"){
      commFuncRadioValues.value[0].disabled = true;
      guiSettings.value.guiState["cal_distance"] = "nipple";
    }
    if (val === "ribcage"){
      commFuncRadioValues.value[1].disabled = true;
      guiSettings.value.guiState["cal_distance"] = "ribcage";
    }
    guiSettings.value.guiSetting["cal_distance"].onChange(calculatorPickerRadios.value);
  }

  function onClockFaceChange(val: string | null){
    commFuncRadioValues.value[2].disabled = true;
    finishBtnDisabled.value = false;
    console.log("clockface timer: ", now.getHours()+":", now.getMinutes()+":", now.getSeconds());
  }

  function onBtnClick(val:string){
    if (!!guiSettings.value){
      calculatorPickerRadios.value = "tumour";
      guiSettings.value.guiState["cal_distance"] = "tumour";
      clockFaceDisabled.value = true;
      finishBtnDisabled.value = true;
      showBtn.value = true;
      calculatorTimerReport("finish")
    }
  }

  function onNextCaseClick(){
    showBtn.value = false;
    emitter.emit("TumourStudy:NextCase");
  }
  
  </script>
  
  <style scoped></style>
  