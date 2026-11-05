<template>
  <HubShell :title="hero.title" :subtitle="hero.subtitle" accent="var(--accent-measurements)">
    <router-view />
  </HubShell>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import HubShell from '../components/HubShell.vue';

const route = useRoute();
const hero = computed(() => route.name === 'UploadMeasurementsDataset'
  ? { title: 'Measurements', subtitle: 'Register SDS measurement datasets so assays can use them as inputs.' }
  : { title: 'Register a measurement dataset',
      subtitle: 'Upload an SDS dataset and annotate it for FHIR if you want. You approve it from its card afterwards.' });
</script>
