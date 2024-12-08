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
        >{{ pinkBtnTitle }}</v-btn>
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
  import { ITumourStudyAppDetail, ICommXYZ } from "@/models/apiTypes";
  import { useRouter, useRoute } from 'vue-router';
  
  type ClockFace = "12:00" | "1:00" | "2:00" | "3:00" | "4:00" | "5:00" | "6:00" | "7:00" | "8:00" | "9:00" | "10:00" | "11:00" | "central";
  // buttons
  const calculatorPickerRadios = ref("nipple");
  const finishBtnDisabled = ref(true);
  const showBtn = ref(false);
  const clockFaceDisabled = ref(true);
  const clockFace = ref(["12:00", "1:00", "2:00", "3:00", "4:00", "5:00", "6:00", "7:00", "8:00", "9:00", "10:00", "11:00", "central"]);
  const selectedClockFace = ref("");
  const pinkBtnTitle = ref("Next Case");
  const router = useRouter();
  
  const commFuncRadioValues = ref([
    // { label: "Tumour", value: "tumour", color: "#4CAF50" },
    { label: "Nipple", value: "nipple", color: "#E91E63", disabled: false },
    { label: "Skin", value: "skin", color: "#FFEB3B", disabled: true },
    { label: "Ribcage", value: "ribcage", color: "#2196F3", disabled: true },
    { label: "ClockFace", value: "clockface", color: "#9C27B0", disabled: true },
  ]);
  
  const guiSettings = ref<any>();
  let nrrdTools:Copper.NrrdTools;
  let workingCase: ITumourStudyAppDetail;
  
  onMounted(() => {
    manageEmitters();
  });
  
  function manageEmitters() {
    emitter.on("TumourStudy:ImageLoaded", (study: ITumourStudyAppDetail) => {
      selectedClockFace.value = "";
      commFuncRadioValues.value[0].disabled = false;
      commFuncRadioValues.value[1].disabled = true;
      commFuncRadioValues.value[2].disabled = true;
      commFuncRadioValues.value[3].disabled = true;
      finishBtnDisabled.value = true;
      clockFaceDisabled.value = true;
      workingCase = study;
      calculatorPickerRadios.value = "nipple";
      guiSettings.value.guiState["cal_distance"] = "";
      setupTumourSpherePosition()
      toggleCalculatorPickerRadios("nipple");
    });
  
    emitter.on("TumourStudy:Status", (status: string, position:number[], distance:number)=>{
      const convertedPosition = {x: customRound(position[0]), y: customRound(position[1]), z: customRound(position[2])};
      calculatorTimerReport(status, convertedPosition, distance);
    })

    // First time init Calculator
    emitter.on("TumourStudy:NrrdTools", (tool: Copper.NrrdTools)=>{
      nrrdTools = tool
      guiSettings.value = nrrdTools.getGuiSettings()
      guiSettings.value.guiState["calculator"] = true;
      guiSettings.value.guiState["sphere"] = false;
      guiSettings.value.guiSetting["calculator"].onChange();
    });

    emitter.on("TumourStudy:AllCasesCompleted", ()=>{
      showBtn.value = true;
      pinkBtnTitle.value = "End Session";
    });
  }

  
function setupTumourSpherePosition(){

  const tumourCenter = workingCase.tumour_position.center;
  nrrdTools.setCalculateDistanceSphere(tumourCenter.x, tumourCenter.y, tumourCenter.z, "tumour");
}


function calculatorTimerReport(status:string, position:ICommXYZ, distance:number){

  switch (status) {
    case "nipple":
        commFuncRadioValues.value[1].disabled = false;
        workingCase.report.nipple.position = position;
        workingCase.report.nipple.distance = distance + " mm";
        break;
      case "skin":
        commFuncRadioValues.value[2].disabled = false;
        workingCase.report.skin.position = position;
        workingCase.report.skin.distance = distance + " mm";
        break;
      case "ribcage":
        commFuncRadioValues.value[3].disabled = false;
        workingCase.report.ribcage.position = position;
        workingCase.report.ribcage.distance = distance + " mm";
        break;
      default:
        break;
    }
}

function toggleCalculatorPickerRadios(val: string | null) {
  const now = new Date();
  const currentTime = now.getTime();
  if (val === "nipple"){
    workingCase.report.start = currentTime;
    workingCase.report.nipple.start = currentTime;
    commFuncRadioValues.value[0].disabled = true;
    guiSettings.value.guiState["cal_distance"] = "nipple";
  }
  if (val === "skin"){
    // "tumour" | "skin" | "nipple" | "ribcage"
    workingCase.report.nipple.end = currentTime;
    workingCase.report.skin.start = currentTime;
    guiSettings.value.guiState["cal_distance"] = "skin";
  }
  if (val === "ribcage"){
    workingCase.report.ribcage.start = currentTime;
    workingCase.report.skin.end = currentTime;
    commFuncRadioValues.value[1].disabled = true;
    guiSettings.value.guiState["cal_distance"] = "ribcage";
  }
  if (val === "clockface"){
    workingCase.report.ribcage.end = currentTime;
    workingCase.report.clock_face.start = currentTime;
    clockFaceDisabled.value = false;
    commFuncRadioValues.value[2].disabled = true;
    guiSettings.value.guiState["cal_distance"] = "";
  }
  guiSettings.value.guiSetting["cal_distance"].onChange(calculatorPickerRadios.value);
}

function onClockFaceChange(val: ClockFace){
  workingCase.report.clock_face.face = val;
  finishBtnDisabled.value = false;
}

function onBtnClick(val:string){
  const now = new Date();
  const currentTime = now.getTime();
  workingCase.report.end = currentTime;
  workingCase.report.clock_face.end = currentTime;

  calculatorPickerRadios.value = "";
  guiSettings.value.guiState["cal_distance"] = "";
  clockFaceDisabled.value = true;
  finishBtnDisabled.value = true;
  showBtn.value = true;
  updateReport(); 
}

function onNextCaseClick(){
  if(pinkBtnTitle.value === "End Session"){
    router.push({name: "Dashboard"});
    return;
  }
  showBtn.value = false;
  emitter.emit("TumourStudy:NextCase");
}

function updateReport(){
  workingCase.report.total_duration = timeDifferenceToHMS(Math.abs((workingCase.report.end as number) - (workingCase.report.start as number)));
  workingCase.report.nipple.duration = timeDifferenceToHMS(Math.abs((workingCase.report.nipple.end as number) - (workingCase.report.nipple.start as number)));
  workingCase.report.skin.duration = timeDifferenceToHMS(Math.abs((workingCase.report.skin.end as number) - (workingCase.report.skin.start as number)));
  workingCase.report.ribcage.duration = timeDifferenceToHMS(Math.abs((workingCase.report.ribcage.end as number) - (workingCase.report.ribcage.start as number)));
  workingCase.report.clock_face.duration = timeDifferenceToHMS(Math.abs((workingCase.report.clock_face.end as number) - (workingCase.report.clock_face.start as number)));
  workingCase.report.start = timestampToHMS(workingCase.report.start as number);
  workingCase.report.end = timestampToHMS(workingCase.report.end as number);
  workingCase.report.skin.start = timestampToHMS(workingCase.report.skin.start as number);
  workingCase.report.skin.end = timestampToHMS(workingCase.report.skin.end as number);
  workingCase.report.nipple.start = timestampToHMS(workingCase.report.nipple.start as number);
  workingCase.report.nipple.end = timestampToHMS(workingCase.report.nipple.end as number);
  workingCase.report.ribcage.start = timestampToHMS(workingCase.report.ribcage.start as number);
  workingCase.report.ribcage.end = timestampToHMS(workingCase.report.ribcage.end as number);
  workingCase.report.clock_face.start = timestampToHMS(workingCase.report.clock_face.start as number);
  workingCase.report.clock_face.end = timestampToHMS(workingCase.report.clock_face.end as number);

  emitter.emit("TumourStudy:CaseReport", workingCase.report);  
}

function customRound(num:number) {
  const decimalPart = num - Math.floor(num);
  
  if (decimalPart > 0.5) {
    return Math.ceil(num);  
  } else {
    return Math.floor(num); 
  }
}

function timestampToHMS(timestamp:number|string) {
  const date = new Date(timestamp);  
  const hours = date.getHours();   
  const minutes = date.getMinutes(); 
  const seconds = date.getSeconds(); 

  const formattedTime = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  return formattedTime;
}

function timeDifferenceToHMS(diffInMillis:number) {

  const hours = Math.floor(diffInMillis / (1000 * 60 * 60)); 
  const minutes = Math.floor((diffInMillis % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diffInMillis % (1000 * 60)) / 1000); 

  const formattedTime = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  return formattedTime;
}
  
</script>

<style scoped></style>
  