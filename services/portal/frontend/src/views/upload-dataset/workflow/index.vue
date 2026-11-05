<template>
  <HubShell :title="hero.title" :subtitle="hero.subtitle" accent="var(--accent-workflows)">
    <router-view />
  </HubShell>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import HubShell from '../components/HubShell.vue';

const route = useRoute();
const hero = computed(() => route.name === 'UploadWorkflowDataset'
  ? { title: 'Workflows', subtitle: 'Register workflows that chain tools into the steps an assay runs.' }
  : { title: 'Register a workflow', subtitle: 'Add its SDS package, annotate it for FHIR if you want, then build it.' });
</script>
