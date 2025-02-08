<template>
  <div>
    <Switcher
      v-if="debugSetting"
      :title="'Debug Mode'"
      :label="switchDebugLabel"
      v-model:controller="debugMode"
      @toggleUpdate="toggleDebug"
    />
    <Switcher
      v-if="stickyNavSetting"
      :title="'Sticky Tool Settings Bar'"
      :label="switchStickyLabel"
      v-model:controller="stickyMode"
      @toggleUpdate="toggleSticky"
    />

    <Dialog 
      :btnText="'Keyboard Settings'"
      btnColor = "deep-orange"
      btnIcon = "mdi-cog"
      @on-open="handleDialogOpen"
      @on-cancel="handleDialogCancel"
      @on-save="handleDialogSave"
    >

    <template #title>
      <h2 class="text-h5 mb-6">Keyboard Settings</h2>
    </template>

    <template #description>
      <p class="mb-4 text-medium-emphasis text-body-2">
        Customize your keyboard shortcuts for Tumour Study Tool. 
        <br/>
        Click `Save` button to save your changes. Click grey area to cancel.
      </p>
    </template>

    <div v-if="keyBoardSetting">
      <div v-for="(d, i) in settingsData" :key="i" class="d-flex align-center justify-space-between px-10">
        <h4 class="pb-3">
          {{ d.label }}
        </h4>
        <div class="w-33">
          <v-text-field 
            v-model="keyboardSettings[d.type]"  
            variant="outlined"
            @keydown="handleKeyDown($event, d.type)"
          ></v-text-field>
        </div>
      </div>
    </div>
    
    <div class="d-flex align-center justify-space-between px-10">
      <h4 class="pb-3">
        Mouse Wheel Mode:
      </h4>
      <div class="w-33">
        <v-select
          label="Select"
          v-model="keyboardSettings.mouseWheel"
          :items="mouseModes"
          variant="outlined"
        ></v-select>
      </div>
    </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import * as Copper from "copper3d";
import Switcher from "@/components/commonBar/Switcher.vue";
import { ref, onMounted, onUnmounted, watch, computed } from "vue";
import Dialog from "@/components/commonBar/Dialog.vue";
import { IKeyboardSettings } from "@/models/apiTypes";


interface Props {
  keyBoardSetting?: boolean;
  stickyNavSetting?: boolean;
  debugSetting?: boolean;
  stick?: boolean;
  nrrdTools?: Copper.NrrdTools;
}

const props = withDefaults(defineProps<Props>(), {
  keyBoardSetting: false,
  stickyNavSetting: false,
  debugSetting: false,
  stick: true,
});

const emit = defineEmits(["updateDebug","updateSticky"]);

// const { nrrdTools } = storeToRefs(useNrrdToolsStore());

const debugMode = ref(false);
const stickyMode = ref(true);
const switchDebugLabel = ref("off");
const switchStickyLabel = ref("on");
const keyboardSettings = ref<IKeyboardSettings>({
  draw: '',
  undo: "",
  contrast: [],
  crosshair: "",
  mouseWheel: "",
});
const mouseModes = ref([
  "Scroll:Zoom",
  "Scroll:Slice",
]);

const settingsData = ref([
  {
    label: "Key for Draw Mode:",
    type: "draw",
  },
  {
    label: "Key for Undo:",
    type: "undo",
  },
  {
    label: "Key for Contrast:",
    type: "contrast",
  },
  {
    label: "Key for Crosshair:",
    type: "crosshair",
  },
])

// const toolsKeyBoard = computed(()=>{
//   if (!!nrrdTools.value) {
//     return nrrdTools.value.nrrd_states.keyboardSettings;
//   }else{
//     return keyboardSettings.value;
//   }
// });

watch(
  ()=>props.nrrdTools,
  ()=>{
    keyboardSettings.value = {...props.nrrdTools!.nrrd_states.keyboardSettings};
  });
watch(
  ()=>props.stick,
  (newVal)=>{
    stickyMode.value = newVal;
    switchStickyLabel.value =  stickyMode.value === false ? "off" : "on";
  }
)

function toggleDebug(value: boolean) {
  switchDebugLabel.value = switchDebugLabel.value === "on" ? "off" : "on";
  emit("updateDebug", value);
}

function toggleSticky(value: boolean) {
  switchStickyLabel.value = switchStickyLabel.value === "on" ? "off" : "on";
  emit("updateSticky", value);
}

function handleKeyDown(event: KeyboardEvent, type: string) {
  switch(type) {
    case "draw":
      setTimeout(()=>{
        keyboardSettings.value.draw = event.key;
      },10);
      break;
    case "undo":
      setTimeout(()=>{
        keyboardSettings.value.undo = event.key;
      },10);
      break;
    case "contrast":
      setTimeout(()=>{
        keyboardSettings.value.contrast = [event.key];
      },10);
      break;
    case "crosshair":
      setTimeout(()=>{
        keyboardSettings.value.crosshair = event.key;
      },10);
      break;
  }
}

function handleDialogOpen() {
  props.nrrdTools!.nrrd_states.configKeyBoard = true;
}

function handleDialogCancel() {
  props.nrrdTools!.nrrd_states.configKeyBoard = false;
  keyboardSettings.value = {...props.nrrdTools!.nrrd_states.keyboardSettings};
  
}
function handleDialogSave() {
  props.nrrdTools!.nrrd_states.configKeyBoard = false;
  props.nrrdTools!.nrrd_states.keyboardSettings = {...keyboardSettings.value as any};
  props.nrrdTools!.updateMouseWheelEvent();
}

</script>

<style scoped></style>
