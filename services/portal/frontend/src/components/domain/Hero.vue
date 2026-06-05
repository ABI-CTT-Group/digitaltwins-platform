<template>
  <header class="page-hero">
    <h1 class="page-hero__title">{{ title }}</h1>
    <p v-if="subtitle" class="page-hero__sub">{{ subtitle }}</p>
    <div v-if="$slots.default" class="page-hero__actions">
      <slot></slot>
    </div>
  </header>
</template>

<script setup lang="ts">
// Generic, reusable page header (title + subtitle + optional action slot).
// Used by the upload-dataset pages and any other sub-page that wants a calm,
// on-system heading. The animated landing hero lives separately in HomeHero.vue.
defineProps({
  title: {
    type: String,
    default: 'Accelerating Development of Digital Twin and AI-Driven Workflows',
  },
  subtitle: {
    type: String,
    default: 'Seamlessly integrate digital twin and AI technologies into clinical and research environments',
  },
});
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&display=swap');

.page-hero {
  text-align: center;
  padding: clamp(24px, 5vh, 52px) 16px clamp(18px, 3.5vh, 34px);
}
.page-hero__title {
  margin: 0 auto;
  max-width: 24ch;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  line-height: 1.14;
  letter-spacing: -0.01em;
  color: #fff;
}
.page-hero__sub {
  margin: 14px auto 0;
  max-width: 52ch;
  font-family: "Nunito", sans-serif;
  font-size: clamp(0.92rem, 1.3vw, 1.04rem);
  line-height: 1.55;
  color: #a4bac4;
}
.page-hero__actions {
  margin-top: 22px;
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
