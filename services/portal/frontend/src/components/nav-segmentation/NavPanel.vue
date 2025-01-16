<template>
  <v-card class="mx-auto">
    <v-list v-model:opened="open">
      <v-list-item
        prepend-icon="mdi-tools"
        color="success"
        title="Tools Core Settings"
      ></v-list-item>
      <ImageCtl />
      <OperationCtl />
      <NavRightPanelCore />
      <SysOpts>
        <SysOptsCtl :key-board-setting="true" :debug-setting="true" :sticky-nav-setting="true" :stick="stickMode" :nrrd-tools="nrrdTools" @update-debug="handleUpdateDebug" @update-sticky="handleUpdateSticky"/>
      </SysOpts>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import ImageCtl from "./tools/NrrdImageCtl.vue";
import OperationCtl from "./tools/OperationCtl.vue";
import NavRightPanelCore from "./NavRightPanel.vue";
import SysOpts from "../nav-components/sysopt/SysOpts.vue";
import SysOptsCtl from "../nav-components/sysopt/SysOptsCtl.vue";
import emitter from "@/plugins/custom-emitter";
import * as Copper from "copper3d";
const open = ref(["Cases"]);

const stickMode = ref<boolean>(true);
const nrrdTools = ref<Copper.NrrdTools>();

onMounted(()=>{
  manageEmitters();
})

function manageEmitters() {
  emitter.on("IntroGuide:OperationStatus", emitterOnOperationStatus);
  emitter.on("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox)
  emitter.on("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox)
  emitter.on("Core:NrrdTools", emitterOnNrrdTools)
  emitter.on("Common:DrawerStatus", emitterOnDrawerStatus);
}

const emitterOnOperationStatus = (val:string)=>{
  if(val==="open" && !open.value.includes("Operation")){
    open.value.push("Operation")
  }
}
const emitterOnOpenCalculatorBox = (val:string)=>{
  open.value.push(val)
}
const emitterOnCloseCalculatorBox = (val:string)=>{
  open.value = open.value.filter(item => item !== val)
}
const emitterOnNrrdTools = (val: Copper.NrrdTools)=>{
  nrrdTools.value = val;
};
const emitterOnDrawerStatus = (val:boolean)=>{
  stickMode.value = val;
}

function handleUpdateDebug(value:boolean){
  emitter.emit("Common:DebugMode", value);
}

function handleUpdateSticky(value:boolean){
  emitter.emit("Common:NavStickyMode", value);
}

onUnmounted(()=>{
  emitter.off("IntroGuide:OperationStatus", emitterOnOperationStatus);
  emitter.off("Common:OpenCalculatorBox", emitterOnOpenCalculatorBox)
  emitter.off("Common:CloseCalculatorBox", emitterOnCloseCalculatorBox)
  emitter.off("Core:NrrdTools", emitterOnNrrdTools)
  emitter.off("Common:DrawerStatus", emitterOnDrawerStatus);
})

</script>

<style lang="scss"></style>
