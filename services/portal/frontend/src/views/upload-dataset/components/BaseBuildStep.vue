<template>
  <v-container class="fill-height d-flex flex-column build-step-container">
    <div class="d-flex flex-column align-center justify-center flex-grow-1 text-center">
      <v-icon size="64" color="cyan-darken-1">mdi-rocket-launch</v-icon>

      <h2 class="mt-4 text-cyan">
        {{ type === 'workflow' ? 'Build Workflow' : 'Build & Test Tool' }}
      </h2>

      <p class="text-grey">
        Your {{ type === 'workflow' ? 'workflow' : 'tool' }} "<strong>{{ !!data && data.name }}</strong>" has been submitted and is ready to build.
      </p>
    </div>

    <div class="d-flex flex-row justify-center">
      <v-btn
        color="red"
        :text="'close'"
        variant="tonal"
        :width="200"
        rounded="md"
        class="hover-animate ma-5"
        @click="handleClose"
      ></v-btn>
      <v-btn
        color="success"
        :text="type === 'workflow' ? 'Build Workflow' : 'Build Tool'"
        variant="tonal"
        :width="200"
        rounded="md"
        class="hover-animate ma-5"
        @click="handleBuild"
      ></v-btn>
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import { IWorkflowResponse, ToolResponse } from '@/models/types';

const props = defineProps<{
  type: 'workflow' | 'tool'
  data: IWorkflowResponse | ToolResponse | undefined
}>();
const emit = defineEmits(["close", "build"])

const handleBuild = () => {
  if (!props.data){
    console.warn("Build start failed! No info in Build stepper.")
    return
  }
  emit("build", props.data.id)
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
