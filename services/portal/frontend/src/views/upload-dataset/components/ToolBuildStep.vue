<template>
  <v-container class="fill-height d-flex flex-column build-step-container">
    <div class="d-flex flex-column align-center justify-center flex-grow-1 text-center">
      <v-icon size="64" color="cyan-darken-1">mdi-rocket-launch</v-icon>

      <h2 class="mt-4 text-cyan">Build & Test Plugin</h2>

      <p class="text-grey">
        Your plugin "<strong>{{ !!tool && tool.name }}</strong>" has been submitted and is ready to build and test.
      </p>
    </div>

     <div class="d-flex flex-row justify-center">
            <v-btn
                color="red"
                :text="'close'"
                variant="tonal"
                :width="150"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleClose"
            ></v-btn>
            <v-btn
                color="success"
                :text="'BUild Tool'"
                variant="tonal"
                :width="150"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleBuild"
            ></v-btn>
        </div>
  </v-container>

</template>

<script lang="ts" setup>
import { ref } from "vue";
import { PluginResponse } from '@/models/uiTypes';

const props = defineProps<{
  tool: PluginResponse | undefined
}>();
const emit = defineEmits(["close", "build"])

const handleBuild = () => {
  if (!props.tool){
    console.warn("Build start failed! No tool information in Build stepper.")
    return
  }
  emit("build", props.tool.id)
}
const handleClose = () => {
  emit("close")
}
</script>

<style scoped>
.build-step-container{
  min-height: 40vh;
}
</style>
