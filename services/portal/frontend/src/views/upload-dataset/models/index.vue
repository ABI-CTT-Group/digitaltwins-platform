<template>
  <HubShell :title="hero.title" :subtitle="hero.subtitle" accent="var(--accent-models)">
    <router-view />
  </HubShell>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import HubShell from '../components/HubShell.vue';

const route = useRoute();
const hero = computed(() => route.name === 'UploadModelDataset'
  ? { title: 'Models', subtitle: 'Register trained models (SDS datasets) so assays and inference workflows can use them.' }
  : { title: 'Register a model',
      subtitle: 'Upload an SDS model dataset and add FHIR details if you want. You approve it from its card afterwards.' });
</script>
