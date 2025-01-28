<template>
    <CalculatorUI 
      :study-radios-value="commFuncRadioValues"
      :clock-face-disabled="clockFaceDisabled"
      :enable-clock-face="isShowClockFace"
      :finish-btn-disabled="finishBtnDisabled"
      :show-next-btn="showBtn"
      :pink-btn-title="pinkBtnTitle"
      v-model:clock-face="selectedClockFace"
      v-model:radios="calculatorPickerRadios"
      @update:selected-clock-face="onClockFaceChange"
      @update:finish-click="onFinishBtnClick"
      @update:next-case-click="onNextCaseClick"
      @update:selected-radio="toggleCalculatorPickerRadios"
    />
</template>
  
<script setup lang="ts">
import CalculatorUI from "@/components/nav-components/tumour-study-calculator-ui/CalculatorUI.vue";
import { ref, onMounted, onUnmounted, computed} from "vue";
import * as Copper from "copper3d";
import emitter from "@/plugins/custom-emitter";
import { ITumourStudyAppDetail, ICommXYZ } from "@/models/apiTypes";
import { useRouter, useRoute } from 'vue-router';
import { setTumourStudyPointPosition } from "@/components/utils";

interface IRadiosValue {
  label: string;
  value: string;
  color: string;
  disabled: boolean;
}
type ClockFace = "12:00" | "1:00" | "2:00" | "3:00" | "4:00" | "5:00" | "6:00" | "7:00" | "8:00" | "9:00" | "10:00" | "11:00" | "central";
// buttons
const calculatorPickerRadios = ref("nipple");
const finishBtnDisabled = ref(true);
const showBtn = ref(false);
const clockFaceDisabled = ref(true);
const isShowClockFace = ref(true);
const selectedClockFace = ref("");
const pinkBtnTitle = ref("Next Case");
const router = useRouter();
const fromWhichApp = ref("");

const commFuncRadioValues = ref<Array<IRadiosValue>>([]);

const guiSettings = ref<any>();
let nrrdTools: Copper.NrrdTools;
let workingCase: ITumourStudyAppDetail;


onMounted(() => {
  manageEmitters();
});

// const guiSettings = computed(()=>{
//   if(!!nrrdTools.value){
//     return nrrdTools.value.getGuiSettings()
//   }else{
//     return undefined;
//   }
// })

function manageEmitters() {

  emitter.on("Common:OnAppMounted", emitterOnAppMounted);
  emitter.on("TumourStudy:ImageLoaded", emitterOnImageLoaded);

  emitter.on("TumourStudy:Status", emitterOnStatus);

  // First time init Calculator
  emitter.on("Core:NrrdTools", emitterOnNrrdTools);

  emitter.on("TumourStudy:AllCasesCompleted", emitterOnAllCasesCompleted);
}

const emitterOnAppMounted = (from:string) => {
  fromWhichApp.value = from;
  switch(from){
    case "TumourStudy:User-Tumour-Distance-Calculation":
    commFuncRadioValues.value = [
            { label: "Nipple", value: "nipple", color: "#E91E63", disabled: false },
            { label: "Skin", value: "skin", color: "#FFEB3B", disabled: true},
            { label: "Ribcage", value: "ribcage", color: "#2196F3", disabled: true},
            { label: "ClockFace", value: "clockface", color: "#9C27B0", disabled: true},
        ]
      break;
    case "TumourStudy:Admin-TumourCenter":
      commFuncRadioValues.value = [
            { label: "Tumour", value: "tumour", color: "#4CAF50", disabled: false},
        ]
      break;
    case "TumourStudy:Admin-TumourAssisted":
      commFuncRadioValues.value = [
            { label: "Tumour", value: "tumour", color: "#4CAF50", disabled: false},
            { label: "Nipple", value: "nipple", color: "#E91E63", disabled: false},
            { label: "Skin", value: "skin", color: "#FFEB3B", disabled: false},
            { label: "Ribcage", value: "ribcage", color: "#2196F3", disabled: false},
            { label: "ClockFace", value: "clockface", color: "#9C27B0", disabled: false}]
      break;
    default:
      commFuncRadioValues.value = [
            { label: "Tumour", value: "tumour", color: "#4CAF50", disabled: false},
            { label: "Nipple", value: "nipple", color: "#E91E63", disabled: false},
            { label: "Skin", value: "skin", color: "#FFEB3B", disabled: true},
            { label: "Ribcage", value: "ribcage", color: "#2196F3", disabled: true},
            { label: "ClockFace", value: "clockface", color: "#9C27B0", disabled: true},
        ];
      break;
  }
}

const emitterOnImageLoaded = (study: ITumourStudyAppDetail) => {

  configRadiosUI();
  workingCase = study;
  // @ts-ignore
  guiSettings.value!.guiState["cal_distance"] = "";
  setupTumourSpherePosition();
  if(fromWhichApp.value === "TumourStudy:Admin-TumourAssisted"){
    setupSkinRibcageNipplePosition();
  }
  toggleCalculatorPickerRadios(calculatorPickerRadios.value);
}

const emitterOnStatus = (status: string, position:number[], distance:number)=>{
  const convertedPosition = {x: position[0], y: position[1], z: position[2]};
  calculatorTimerReport(status, convertedPosition, distance);
}

const emitterOnNrrdTools = (tool: Copper.NrrdTools)=>{
  nrrdTools = tool
  guiSettings.value = nrrdTools.getGuiSettings()
  guiSettings.value!.guiState["calculator"] = true;
  guiSettings.value!.guiState["sphere"] = false;
  guiSettings.value!.guiSetting!["calculator"].onChange();
}

const emitterOnAllCasesCompleted = ()=>{
  showBtn.value = true;
  pinkBtnTitle.value = "End Session";
}

const configRadiosUI = () => {
  switch(fromWhichApp.value){
    case "TumourStudy:User-Tumour-Distance-Calculation":
      commFuncRadioValues.value[0].disabled = false;
      commFuncRadioValues.value[1].disabled = true;
      commFuncRadioValues.value[2].disabled = true;
      commFuncRadioValues.value[3].disabled = true;
      selectedClockFace.value = "";
      finishBtnDisabled.value = true;
      clockFaceDisabled.value = true;
      isShowClockFace.value = true;
      calculatorPickerRadios.value = "nipple";
      break;
    case "TumourStudy:Admin-TumourCenter":
      isShowClockFace.value = false;
      finishBtnDisabled.value = false;
      calculatorPickerRadios.value = "tumour";
      break;
    case "TumourStudy:Admin-TumourAssisted":
      finishBtnDisabled.value = false;
      calculatorPickerRadios.value = "tumour";
      break;
    default:
      break;
  }
};


function setupTumourSpherePosition(){
  const tumourCenter = workingCase.tumour_window.center;
  setTumourStudyPointPosition(nrrdTools as Copper.NrrdTools, tumourCenter, "tumour");
}

function setupSkinRibcageNipplePosition(){
  const report = workingCase.report;
 
  if(!!report.nipple.position){
    setTumourStudyPointPosition(nrrdTools as Copper.NrrdTools, report.nipple.position, "nipple");
  }
  if(!!report.skin.position){
    setTumourStudyPointPosition(nrrdTools as Copper.NrrdTools, report.skin.position, "skin");
  }
  if(!!report.ribcage.position){
    setTumourStudyPointPosition(nrrdTools as Copper.NrrdTools, report.ribcage.position, "ribcage");
  }
  selectedClockFace.value = report.clock_face.face;
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
  if (val === "tumour"){
    guiSettings.value.guiState["cal_distance"] = "tumour";
  }
  if (val === "nipple"){
    workingCase.report.start = currentTime;
    workingCase.report.nipple.start = currentTime;
    guiSettings.value.guiState["cal_distance"] = "nipple";
  }
  if (val === "skin"){
    // "tumour" | "skin" | "nipple" | "ribcage"
    workingCase.report.nipple.end = currentTime;
    workingCase.report.skin.start = currentTime;
    commFuncRadioValues.value[0].disabled = true;
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

function onClockFaceChange(val: any){
  workingCase.report.clock_face.face = val;
  finishBtnDisabled.value = false;
}

function onFinishBtnClick(val:string){
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
  workingCase.report.spacing = {
    x: nrrdTools.nrrd_states.voxelSpacing[0],
    y: nrrdTools.nrrd_states.voxelSpacing[1],
    z: nrrdTools.nrrd_states.voxelSpacing[2]
  }
  workingCase.report.origin = {
    x: nrrdTools.nrrd_states.spaceOrigin[0],
    y: nrrdTools.nrrd_states.spaceOrigin[1],
    z: nrrdTools.nrrd_states.spaceOrigin[2]
  }
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

onUnmounted(() => {
  emitter.off("Common:OnAppMounted", emitterOnAppMounted);
  emitter.off("TumourStudy:ImageLoaded", emitterOnImageLoaded);
  emitter.off("TumourStudy:Status", emitterOnStatus);
  emitter.off("Core:NrrdTools", emitterOnNrrdTools);
  emitter.off("TumourStudy:AllCasesCompleted", emitterOnAllCasesCompleted);
});
</script>

<style scoped></style>
  