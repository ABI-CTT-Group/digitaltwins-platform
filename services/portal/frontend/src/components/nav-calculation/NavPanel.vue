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
      <SysOpts />
    </v-list>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import ImageCtl from "./tools/NrrdImageCtl.vue";
import OperationCtl from "./tools/OperationCtl.vue";
import SysOpts from "./SysOpts.vue";
const open = ref(["Cases", "Operation", "Calculator"]);

onMounted(()=>{
  manageEmitters();
})

function manageEmitters() {
  // emitter.on("guide_to_operation_status", (val: string)=>{
  //   if(val==="open" && !open.value.includes("Operation")){
  //     open.value.push("Operation")
  //   }
  // });
}
</script>

<style lang="scss"></style>
