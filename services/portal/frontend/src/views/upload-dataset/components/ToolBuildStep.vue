<template>
  <v-container class="fill-height d-flex align-center justify-center">
    <div class="text-center">
      <v-icon size="64" color="cyan-darken-1">mdi-rocket-launch</v-icon>

      <h2 class="mt-4">Build & Test Plugin</h2>

      <p class="text-grey">
        Your plugin "<strong>{{ }}</strong>" has been submitted and is ready to build and test.
      </p>
    </div>
  </v-container>
</template>

<script setup>
import { ref } from "vue";
import { PluginResponse } from '@/models/uiTypes';

const props = defineProps<{
  tool: PluginResponse
}>();

const pluginName = ref("MyAwesomePlugin");
</script>

<style scoped>
</style>
