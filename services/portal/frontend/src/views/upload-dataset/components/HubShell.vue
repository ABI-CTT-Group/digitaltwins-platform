<template>
  <section class="hub" :style="{ '--accent': accent }">
    <BackLink to="CatalogueDashboardView" label="Catalogue" sticky class="hub__back" />
    <header class="hub__head">
      <h1 class="hub__title">{{ title }}</h1>
      <p v-if="subtitle" class="hub__sub">{{ subtitle }}</p>
    </header>
    <slot />
  </section>
</template>

<script setup lang="ts">
// The frame of a dataset registration hub and its wizard: the way back to the catalogue, the page
// title and one line on what the page is for. Left-aligned at the catalogue landing's width so the
// hubs read as part of the same catalogue.
import BackLink from '@/components/common/BackLink.vue';

withDefaults(defineProps<{ title: string; subtitle?: string; accent?: string }>(), {
  subtitle: '',
  accent: 'var(--accent-tools)',
});
</script>

<style scoped>
.hub {
  max-width: 1120px;
  margin: 0 auto;
  padding: 16px clamp(16px, 4vw, 40px) 64px;
  font-family: var(--font-ui);
  color: var(--text);
}
.hub__back { margin-bottom: clamp(20px, 4vh, 36px); }
.hub__head { margin-bottom: clamp(20px, 4vh, 32px); }
.hub__title {
  margin: 0;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: clamp(2.2rem, 5vw, 3.4rem);
  line-height: 1.02;
  letter-spacing: -0.015em;
  color: #fff;
}
.hub__sub {
  margin: 12px 0 0;
  max-width: 60ch;
  font-size: 1rem;
  line-height: 1.55;
  color: var(--text-dim);
}
</style>
