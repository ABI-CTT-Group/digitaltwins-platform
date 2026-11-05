<template>
  <v-container class="fill-height d-flex flex-column build-step-container">
    <div class="d-flex flex-column align-center justify-center flex-grow-1 text-center">
      <v-icon size="64" color="#5fd6e8">mdi-rocket-launch</v-icon>

      <h2 class="mt-4 step-title">Build {{ data?.name }}</h2>

      <p class="step-sub">
        The build runs in the background: you can follow it from the {{ type === 'workflow' ? 'workflow' : 'tool' }}'s card.
        Once it's built, approve it to add it to the platform.
      </p>
    </div>

    <p v-if="submitError" class="step-error" role="alert">
      <v-icon icon="mdi-alert-circle-outline" size="18" /> {{ submitError }}
    </p>
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="#9fb4bf"
        text="Cancel"
        variant="text"
        :width="200"
        rounded="lg"
        class="text-none ma-5"
        :disabled="starting"
        @click="emit('close')"
      ></v-btn>
      <v-btn
        color="#5fd6e8"
        text="Build"
        variant="tonal"
        :width="200"
        rounded="lg"
        class="text-none ma-5"
        :loading="starting"
        :disabled="starting"
        @click="handleBuild"
      ></v-btn>
    </div>
  </v-container>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import type { WorkflowResponse, ToolResponse } from '@/models/types';
import { describeApiError } from './apiError';

const props = defineProps<{
  type: 'workflow' | 'tool'
  data: WorkflowResponse | ToolResponse | undefined
  /** Starts the build; a failure stays on this step with its reason. */
  submit: (id: string) => Promise<void>
}>();
const emit = defineEmits(["close"])

const starting = ref(false)
const submitError = ref('')

const handleBuild = async () => {
  if (!props.data) return
  starting.value = true
  submitError.value = ''
  try {
    await props.submit(props.data.id)
  } catch (err) {
    submitError.value = describeApiError(err, 'Starting the build')
  } finally {
    starting.value = false
  }
}
</script>

<style scoped>
.build-step-container{
  min-height: 40vh;
}
.step-title {
  font-family: var(--font-title);
  font-weight: 500;
  color: #fff;
}
.step-sub { color: #9fb4bf; max-width: 60ch; }
</style>
