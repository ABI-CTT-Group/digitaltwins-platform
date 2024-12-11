<template>
  <div>
    <Dialog 
      @on-open="handleDialogOpen"
      @on-cancel="handleDialogCancel"
      @on-save="handleDialogSave"
    >

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
// import * as Copper from "@/ts/index";
import { ref, onMounted, onUnmounted } from "vue";
import Dialog from "@/components/commonBar/Dialog.vue";
import { IKeyboardSettings } from "@/models/apiTypes";
import emitter from "@/plugins/custom-emitter";

const nrrdTools = ref<Copper.NrrdTools>();
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
    label: "Key for Crosshair:",
    type: "crosshair",
  },
])


onMounted(() => {
  manageEmitters();
});

function manageEmitters() {
  emitter.on("TumourStudy:NrrdTools", (tool: Copper.NrrdTools)=>{
    nrrdTools.value = tool;
    keyboardSettings.value = {...nrrdTools.value!.nrrd_states.keyboardSettings};
  });
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
  nrrdTools.value!.nrrd_states.configKeyBoard = true;
}

function handleDialogCancel() {
  nrrdTools.value!.nrrd_states.configKeyBoard = false;
  keyboardSettings.value = {...nrrdTools.value!.nrrd_states.keyboardSettings};
  
}
function handleDialogSave() {
  nrrdTools.value!.nrrd_states.configKeyBoard = false;
  nrrdTools.value!.nrrd_states.keyboardSettings = {...keyboardSettings.value as any};
  nrrdTools.value!.updateMouseWheelEvent();
}

</script>

<style scoped></style>
