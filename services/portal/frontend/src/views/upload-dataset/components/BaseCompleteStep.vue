<template>
  <v-container class="fill-height d-flex flex-column build-step-container">
    <div class="d-flex flex-column align-center justify-center flex-grow-1 text-center">
      <v-icon size="64" color="#5fd6e8">mdi-cog-sync</v-icon>

      <h2 class="mt-4 step-title">
        {{ type === 'workflow' ? 'Workflow Build in Progress' : 'Workflow Tool Build in Progress' }}
      </h2>

      <p class="step-sub">
        Your {{ type === 'workflow' ? 'workflow' : 'workflow tool' }} "{{ data?.name }}" is currently being built. Once the build is completed,
        you will be able to upload its dataset to the <strong>DigitalTWINS</strong> platform.
      </p>
    </div>

    <div class="d-flex flex-row justify-center">
      <v-btn
        color="#5fd6e8"
        text="Done"
        variant="tonal"
        :width="150"
        rounded="lg"
        class="text-none ma-5"
        @click="handleDone"
      ></v-btn>
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import { WorkflowResponse, ToolResponse } from '@/models/types';

const props = defineProps<{
  type: 'workflow' | 'tool'
  data: WorkflowResponse | ToolResponse | undefined
}>();

const emit = defineEmits(["done"])

const handleDone = () => {
  emit("done", props.data?.id)
}
</script>

<style scoped>
.build-step-container {
  min-height: 40vh;
}
.step-title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  color: #fff;
}
.step-sub { color: #9fb4bf; }
</style>
