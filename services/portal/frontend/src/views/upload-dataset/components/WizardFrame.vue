<template>
  <div class="wizard" :style="{ '--wizard-accent': accent }">
    <!-- Not clickable: the URL holds the step, and step 1 can't run again once the item exists. -->
    <v-stepper :model-value="current" alt-labels class="wizard__stepper">
      <v-stepper-header>
        <template v-for="(title, i) in steps" :key="title">
          <v-divider v-if="i > 0" />
          <v-stepper-item :title="title" :value="i + 1" :color="accent" :complete="current > i + 1" />
        </template>
      </v-stepper-header>
    </v-stepper>
    <p class="wizard__step-compact">Step {{ current }} of {{ steps.length }}: {{ steps[current - 1] }}</p>

    <slot name="summary" />
    <div class="wizard__pane"><slot /></div>
  </div>
</template>

<script setup lang="ts">
/** The frame every registration wizard shares: its steps (a compact "Step n of m" on phones) and one pane. */
withDefaults(defineProps<{ steps: string[]; current: number; accent?: string }>(), { accent: '#5fd6e8' });
</script>

<style scoped>
.wizard {
  max-width: 1080px;
  margin: 0 auto;
  padding: clamp(12px, 3vw, 28px);
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(8, 18, 26, 0.55);
  font-family: var(--font-ui);
}
.wizard__stepper { background: transparent !important; box-shadow: none !important; }
.wizard__step-compact { display: none; margin: 0 0 12px; font-size: 0.9375rem; font-weight: 600; color: var(--text); }
.wizard__pane {
  min-height: 40vh;
  padding: clamp(8px, 2vw, 16px);
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.02);
}
@media (max-width: 640px) {
  .wizard__stepper { display: none; }
  .wizard__step-compact { display: block; }
}
</style>
