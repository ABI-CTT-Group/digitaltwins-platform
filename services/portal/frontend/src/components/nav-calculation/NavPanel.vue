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
      <SysOpts>
        <SysOptsCtl :nrrd-tools="nrrdTools"/>
      </SysOpts>
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import ImageCtl from "./tools/NrrdImageCtl.vue";
import OperationCtl from "./tools/OperationCtl.vue";
import SysOpts from "../nav-components/sysopt/SysOpts.vue";
import SysOptsCtl from "../nav-components/sysopt/SysOptsCtl.vue";
import emitter from "@/plugins/custom-emitter";
import * as Copper from "copper3d";

const open = ref(["Cases", "Operation", "Calculator"]);
const nrrdTools = ref<Copper.NrrdTools>();

onMounted(()=>{
  manageEmitters();
}) 

function manageEmitters() {
  emitter.on("Core:NrrdTools", emitterOnNrrdTools)
}

const emitterOnNrrdTools = (val:Copper.NrrdTools)=>{
  nrrdTools.value = val;
}

onUnmounted(()=>{
  emitter.off("Core:NrrdTools", emitterOnNrrdTools)
})
</script>

<style lang="scss"></style>
