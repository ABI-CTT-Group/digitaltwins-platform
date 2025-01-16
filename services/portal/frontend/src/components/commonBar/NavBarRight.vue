<template>
  <div class="nav dark guide-right-nav-tool" ref="nav_container">
    <div class="content" id="right_nav_bar" @dblclick.stop>

      <div v-show="showDragSlider && panelWidth >= 600 ? true : false" :class="panelWidth >1000 ? 'mx-6 px-6 slider-lg':'slider-sm'">
        <v-slider
        
        class="mt-5"
        v-model="slider"
        :color="sliderColor"
        thumb-label
        :disabled="sliderDisabled"
        :max="sliderMax"
        :min="sliderMin"
        :step="sliderStep"
        @update:modelValue="toggleSlider"
      ></v-slider>
      </div>
        
      <div class="arrows">
        <div v-for="view in viewData" class="right-views" :class="view.name">
          <span
          v-for="item in view.data"
          :class="{ 'disabled': isBtnDisabled }"
          @click.stop="onSigleClick(item.label)"
          @dblclick.stop="onDoubleClick(item.label)"
        >
          
          <i class="switch_font" v-if="item.label=='reset'">
            <ion-icon name="refresh-outline"></ion-icon>
          </i>

          <i class="switch_font" v-else-if="item.label=='3dview'">
            <ion-icon name="walk-outline"></ion-icon>
          </i>

          <i v-else>
            <img class="image" v-if="darkMode" :src="item.img_white" alt="" />
            <img class="image" v-else :src="item.img_blank" alt="" />
          </i>

          <v-tooltip activator="parent" location="top">{{
            item.name
          }}</v-tooltip>
        </span>
        </div>
        
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, toRefs, reactive, onUnmounted, watch} from "vue";
import sagittalImg_white from "@/assets/images/person_left_view_white.png";
import axialImg_white from "@/assets/images/person_top_down_white.png";
import coronalImg_white from "@/assets/images/person_anterior_white.png";
import sagittalImg_blank from "@/assets/images/person_left_view.png";
import axialImg_blank from "@/assets/images/person_top_down.png";
import coronalImg_blank from "@/assets/images/person_anterior.png";
import clockImg from "@/assets/images/clock_white.png";
import resetImg from "@/assets/images/reset.png";
import emitter from "@/plugins/custom-emitter";
import {PanelOperationManager} from "@/plugins/view-utils/utils-right"

type Props = {
  panelWidth: number;
  settings?:{
      panelOperator: PanelOperationManager;
      dimensions: number[];
      spacing: number[];
      currentValue: number[];
  };
};
interface ISliderView{
    color:string,
    max:number,
    min:number,
    value:number
}

const props = withDefaults(defineProps<Props>(), {
  panelWidth: 1000,
});

const { panelWidth } = toRefs(reactive(props));
const showDragSlider = ref(false)

const viewData = {
  twoDView:{
    name: "guide-right-twoD-view",
    data: [{
      name: "Sagittal view",
      label: "sagittal",
      img:null,
      img_white: sagittalImg_white,
      img_blank: sagittalImg_blank,
    },
    {
      name: "Axial view",
      label: "axial",
      img:null,
      img_white: axialImg_white,
      img_blank: axialImg_blank,
     },
    {
      name: "Coronal view",
      label: "coronal",
      img:null,
      img_white: coronalImg_white,
      img_blank: coronalImg_blank,
    },]
  },
  threeDView:{
    name: "guide-right-threeD-view",
    data:[{
        name: "3D view",
        label: "3dview",
        img:null,
        img_white: "",
        img_blank: "",
      },
      {
        name: "Reset views",
        label: "reset",
        img: resetImg,
        img_white: "",
        img_blank: "",
      },]

  }
}

const slider = ref(0);
const sliderColor = ref("grey");
const sliderDisabled = ref(true);
const sliderMax = ref(100);
const sliderMin = ref(0);
const sliderStep = ref(1);
let operator:PanelOperationManager|null = null;

const sliderViews = {
  sagittal:{
    color:"green-darken-2",
    max:0,
    min:0,
    value:0
  },
  axial:{
    color:"deep-orange-darken-2",
    max:0,
    min:0,
    value:0
  },
  coronal:{
    color:"cyan-darken-2",
    max:0,
    min:0,
    value:0
  },
  default:{
    color:"grey",
    max:0,
    min:0,
    value:0
  }
}

let sliderSettings:ISliderView = sliderViews.default;

const darkMode = ref(true);
const isBtnDisabled = ref(true);
const nav_container = ref<HTMLDivElement>();
const emit = defineEmits(["onViewSingleClick", "onViewDoubleClick"]);

const onSigleClick = (view: string) => {
  if (!isBtnDisabled.value) {
      mountSlider(view)
      emit("onViewSingleClick", view);
    }
};

const onDoubleClick = (view: string) => {
  if (!isBtnDisabled.value) {
    emit("onViewDoubleClick", view);
  }
};

onMounted(() => {
  manageEmitters();
});

const manageEmitters = () => {
  emitter.on("Common:ToggleAppTheme", emitterOnToggleAppTheme);
  // switch cases
  emitter.on("Segmentation:CaseDetails", emitterOnCaseDetails)
};

const emitterOnToggleAppTheme = () => {
  darkMode.value = !darkMode.value;
  nav_container.value?.classList.toggle("dark");
}

const emitterOnRightPanelSliderSettingValueUpdated = (settings:any)=>{
  
}

const emitterOnCaseDetails = ()=>{
  isBtnDisabled.value = true;
  mountSlider("reset")
}

function mountSlider(view:string){
  
  switch (view) {
    case "sagittal":
      sliderSettings = sliderViews.sagittal;
      break;
    case "axial":
      sliderSettings = sliderViews.axial;
      break;
    case "coronal":
      sliderSettings = sliderViews.coronal;
      break;
    default:
      sliderSettings = sliderViews.default;
      break;
  }

  slider.value = sliderSettings.value;
  sliderColor.value = sliderSettings.color;
  sliderMax.value = sliderSettings.max;
  sliderMin.value = sliderSettings.min;

  if(view === "reset" || view === "3dview"){
    sliderDisabled.value = true;
    showDragSlider.value = false;
  }else{
    sliderDisabled.value = false;
    showDragSlider.value = true;
  }
}

function toggleSlider(val: number) {
  if(operator!==null){

    setTimeout(()=>{
     !!operator && operator.updateSliceIndex(val - sliderSettings.value)
    sliderSettings.value = val;
    },10)
   
  }
}

watch(()=>props.settings, ()=>{
  if(!!props.settings){
    isBtnDisabled.value = false;
    sliderViews.sagittal.max = props.settings.dimensions[0] - 1;
    sliderViews.axial.max = props.settings.dimensions[2] - 1;
    sliderViews.coronal.max = props.settings.dimensions[1] - 1;
    sliderViews.sagittal.value = props.settings.currentValue[0];
    sliderViews.axial.value = props.settings.currentValue[2];
    sliderViews.coronal.value = props.settings.currentValue[1];
    operator = props.settings.panelOperator as PanelOperationManager;
  }
});

onUnmounted(() => {
  emitter.off("Common:ToggleAppTheme", emitterOnToggleAppTheme);
  emitter.off("Segmentation:CaseDetails", emitterOnCaseDetails)
});
</script>

<style scoped>
.dark .el-slider {
  max-width: 35vw;
  margin-right: 10px;
  --el-slider-main-bg-color: #f4511e !important;
  --el-slider-runway-bg-color: rgba(0, 0, 0) !important;
}

.nav {
  /* position: fixed;
  bottom: 25px;
  left: 10px; */

  height: 60px;
  width: 85%;
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
.nav .content {
  /* position: relative; */
  width: 100%;
  height: 100%;
  /* background-color: #edf1f4; */
  background-color: #f4f4f4;
  padding: 0 20px;
  border-radius: 10px;
  box-shadow: 0 30px 30px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dark .content {
  background: #33393e;
  /* box-shadow: 15px 15px 20px rgba(0, 0, 0, 0.25),
    -15px -15px 20px rgba(255, 255, 255, 0.1); */
  box-shadow: 15px 15px 20px rgba(0, 0, 0, 0.25),
    -5px -10px 15px rgba(255, 255, 255, 0.1);
}

.nav .content .arrows {
  display: flex;
  align-items: center;
}
.nav .content .arrows span {
  position: relative;
  padding: 10px;
  box-shadow: 5px 5px 10px rgba(0, 0, 0, 0.1), -5px -5px 20px #fff;
  margin: 10px;
  cursor: pointer;
  user-select: none;
  min-width: 55px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 1.2em;
  color: #666;
  border: 2px solid #edf1f4;
  box-shadow: 5px 5px 10px rgba(0, 0, 0, 0.1), -5px -5px 10px #fff;
  border-radius: 10px;
  cursor: pointer;
}
.dark .content .arrows span {
  color: #eee;
  border: 2px solid #333;
  box-shadow: 5px 5px 10px rgba(0, 0, 0, 0.25),
    -5px -5px 10px rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
.nav .content .arrows span:active {
  box-shadow: inset 5px 5px 10px rgba(0, 0, 0, 0.1), inset -5px -5px 10px #fff;
  color: #f44336;
}

.dark .content .arrows span:active {
  box-shadow: inset 5px 5px 10px rgba(0, 0, 0, 0.25),
    inset -5px -5px 10px rgba(255, 255, 255, 0.1);
}

.disabled {
  pointer-events: none; 
  opacity: 0.6; 
}
.slider-lg{
  width: 600px;
}

.slider-sm{
  width: 100%;
}

.image {
  width: 1em;
  height: 1em;
}
.switch_font {
  font-size: 1em;
  pointer-events: none;
}
.switch_font:active {
  font-size: 1em;
  color: #f44336;
}

.right-views{
  display: flex;
  flex-direction: row;
}
</style>
