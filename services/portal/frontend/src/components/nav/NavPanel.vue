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
      <SysOpts />
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import ImageCtl from "./tools/NrrdImageCtl.vue";
import OperationCtl from "./tools/OperationCtl.vue";
import RightPanelCore from "./RightPanelCore.vue";
import SysOpts from "./SysOpts.vue";
import emitter from "@/plugins/bus";
const open = ref(["Cases"]);

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
}

</script>

<style lang="scss"></style>
