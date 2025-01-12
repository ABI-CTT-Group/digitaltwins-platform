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
      <RightPanelCore />
      <SysOpts>
        <SysOptsCtl :key-board-setting="true" :debug-setting="true" :sticky-nav-setting="true" :stick="stickMode" :nrrd-tools="nrrdTools" @update-debug="handleUpdateDebug" @update-sticky="handleUpdateSticky"/>
      </SysOpts>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import ImageCtl from "./tools/NrrdImageCtl.vue";
import OperationCtl from "./tools/OperationCtl.vue";
import RightPanelCore from "./RightPanelCore.vue";
import SysOpts from "../nav-components/sysopt/SysOpts.vue";
import SysOptsCtl from "../nav-components/sysopt/SysOptsCtl.vue";
import emitter from "@/plugins/bus";
import * as Copper from "copper3d";
const open = ref(["Cases",]);

const stickMode = ref<boolean>(true);
const nrrdTools = ref<Copper.NrrdTools>();

onMounted(()=>{
  manageEmitters();
})

function manageEmitters() {
  emitter.on("guide_to_operation_status", (val)=>{
    if(val==="open" && !open.value.includes("Operation")){
      open.value.push("Operation")
    }
  });
  emitter.on("open_calculate_box", (val)=>{
    open.value.push(val as string)
  })
  emitter.on("close_calculate_box", (val)=>{
    open.value = open.value.filter(item => item !== val)
  })

  emitter.on("Segmentation:NrrdTool",(val)=>{
    nrrdTools.value = val as Copper.NrrdTools;
  })
  emitter.on("drawer_status", (val)=>{
    stickMode.value = val as boolean;
  });
}

function handleUpdateDebug(value:boolean){
  emitter.emit("show_debug_mode", value);
}

function handleUpdateSticky(value:boolean){
  emitter.emit("set_nav_sticky_mode", value);
}

</script>

<style lang="scss"></style>
