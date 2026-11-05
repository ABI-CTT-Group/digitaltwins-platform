<template>
  <HubShell :title="hero.title" :subtitle="hero.subtitle" accent="var(--accent-tools)">
    <router-view />

    <!-- Single app-level log console, shared by the hub (rebuild / view logs) and the registration
         wizard (first build) via the useLogConsole singleton. Mounted here so it survives moving
         between the hub and its wizard. -->
    <LogConsole
      v-model="logConsole.open.value"
      :kind="logConsole.kind.value"
      :job-id="logConsole.jobId.value"
      :title="logConsole.title.value"
      :started-at="logConsole.startedAt.value"
      :ended-at="logConsole.endedAt.value"
      :initial-status="logConsole.initialStatus.value"
    />
  </HubShell>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import HubShell from '../components/HubShell.vue';
import LogConsole from '../components/LogConsole.vue';
import { useLogConsole } from '@/composables/useLogConsole';

const logConsole = useLogConsole();
const route = useRoute();
const hero = computed(() => route.name === 'UploadToolDataset'
  ? { title: 'Tools', subtitle: 'Register and build the tools that workflows and assays run.' }
  : { title: 'Register a tool', subtitle: 'Add its source, annotate it for FHIR if you want, then build it.' });
</script>
