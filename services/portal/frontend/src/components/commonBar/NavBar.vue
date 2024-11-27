<template>
  <div class="nav dark guide-left-nav-tool" ref="nav_container" >
    <div class="content" id="left_nav_bar" @dblclick.stop>
      <el-slider
        v-model="sliceNum"
        :max="p.max"
        @input="onChangeSlider"
        @click.stop
        show-input
        id="left_nav_slider"
        class="guide-left-slider"
      />
      <div class="arrows">
        <div class="left-views guide-left-views">
          <span @click="onSwitchSliceOrientation('x')">
            <i class="switch_font">Sagittal</i>
          </span>
          <span @click="onSwitchSliceOrientation('z')">
            <i class="switch_font">Axial</i>
          </span>
          <span @click="onSwitchSliceOrientation('y')">
            <i class="switch_font">Coronal</i>
          </span>
        </div>
        

        <span class="save guide-left-sync" @click="onSave()">
          <div>
            <!-- <ion-icon name="save-outline"></ion-icon> -->
            <ion-icon name="sync-outline"></ion-icon>
          </div>
          <div>
            <i>sync</i>
          </div>
        </span>
        <!-- <span @click="openDialog">
          <ion-icon name="cloud-upload-outline"></ion-icon>
        </span> -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, toRefs, watchEffect, onMounted } from "vue";
import emitter from "@/plugins/bus";
// import {throttle2} from "@/views/components/tools";

type Props = {
  fileNum: number;
  min?: number;
  max?: number;
  showContrast?: boolean;
  initSliceIndex?: number;
  immediateSliceNum?: number;
  contrastIndex?: number;
  isAxisClicked?: boolean;
};
const nav_container = ref<HTMLDivElement>();

onMounted(() => {
  emitter.on("toggleTheme", () => {
    nav_container.value?.classList.toggle("dark");
  });
});
let p = withDefaults(defineProps<Props>(), {
  min: 0,
  max: 160,
  immediateSliceNum: 0,
  contrastIndex: 0,
  fileNum: 0,
  showContrast: false,
  isAxisClicked: false,
});
const state = reactive(p);
const { immediateSliceNum, contrastIndex, initSliceIndex, fileNum } =
  toRefs(state);
const sliceNum = ref(0);

let magnification = 1;
let filesNum = 0;
let currentSliderNum = 0;
let isAxis = false;
let isFileChange = false;

let timer:any = undefined;

const emit = defineEmits([
  "onSliceChange",
  "resetMainAreaSize",
  "onChangeOrientation",
  "onOpenDialog",
  "onSave",
]);

const onSave = () => {
  emit("onSave", true);
};

const openDialog = () => {
  emit("onOpenDialog", true);
};

const onSwitchSliceOrientation = (axis: string) => {
  isAxis = true;
  emit("onChangeOrientation", axis);
  isAxis = false;
};

const onMagnificationClick = (factor: number) => {
  magnification += factor;
  if (magnification > 8) {
    magnification = 8;
  }
  if (magnification < 1) {
    magnification = 1;
  }
  emit("resetMainAreaSize", magnification);
};
document.addEventListener("keydown", (ev: KeyboardEvent) => {
  if (ev.key === "ArrowUp") {
    if (currentSliderNum > 0) {
      currentSliderNum -= 1;
      updateSlider();
      emit("onSliceChange", -1);
    }
  }
  if (ev.key === "ArrowDown") {
    if (currentSliderNum < p.max) {
      currentSliderNum += 1;
      updateSlider();
      emit("onSliceChange", 1);
    }
  }
});

const onChangeSlider = () => {
  const step = sliceNum.value - currentSliderNum;
  currentSliderNum += step;
  if (!isAxis && !isFileChange) {
    setTimeout(()=>{emit("onSliceChange", step);},1);  
  }
  isAxis = false;
  isFileChange = false;
};

const updateSlider = () => {
  sliceNum.value = currentSliderNum;
};

watchEffect(() => {
  currentSliderNum =
    immediateSliceNum.value * fileNum.value + contrastIndex.value;
  updateSlider();
});

watchEffect(() => {
  initSliceIndex?.value &&
    (currentSliderNum = (initSliceIndex?.value as number) * fileNum.value);
  updateSlider();
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
  margin: 5px;
  cursor: pointer;
  user-select: none;
  min-width: 25px;
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

.image {
  width: 1em;
  height: 1em;
}
.switch_font {
  font-size: 0.6em;
}
.switch_font:active {
  font-size: 0.6em;
  color: #f44336;
}
.save {
  display: flex;
  flex-direction: column;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
}
.save div {
  padding: -10px 0;
  margin: -10px 0;
}
.save i {
  font-size: 0.5em;
}
.left-views{
  display: flex;
  flex-direction: row;
}
</style>
