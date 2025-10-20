<template>
  <v-container class="fill-height d-flex flex-column build-step-container">
    <div class="d-flex flex-column align-center justify-center flex-grow-1 text-center">
      <v-icon size="64" color="cyan-darken-1">mdi-cog-sync</v-icon>

      <h2 class="mt-4 text-cyan">Workflow Tool Build in Progress</h2>

      <p class="text-grey">
        Your workflow tool "{{ workflow?.name }}" is currently being built. Once the build is completed, 
        you will be able to upload its dataset to the <strong>DigitalTWINS</strong> platform.
      </p>
    </div>

    <div class="d-flex flex-row justify-center">
      <v-btn
        color="success"
        :text="'Done'"
        variant="tonal"
        :width="150"
        rounded="md"
        class="hover-animate ma-5"
        @click="handleDone"
      ></v-btn>
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import { IWrokflowResponse } from '@/models/uiTypes';

const props = defineProps<{
  workflow: IWrokflowResponse | undefined
}>();
const emit = defineEmits(["done"])

const handleDone = () => {
  emit("done", props.workflow?.id)
}
</script>

<style scoped>
.build-step-container {
  min-height: 40vh;
}
</style>
