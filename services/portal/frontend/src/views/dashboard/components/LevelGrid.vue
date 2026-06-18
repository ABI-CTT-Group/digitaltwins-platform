<template>
  <!-- Error -->
  <div v-if="error" class="state state--error">
    <v-icon icon="mdi-alert-circle-outline" size="40"></v-icon>
    <p class="state__title">Couldn't load this level</p>
    <p class="state__sub">{{ error }}</p>
    <button type="button" class="state__retry" @click="$emit('retry')">Try again</button>
  </div>

  <!-- Loading skeletons -->
  <div v-else-if="loading" class="grid" aria-busy="true">
    <div v-for="n in 6" :key="n" class="skeleton"></div>
  </div>

  <!-- Empty -->
  <div v-else-if="!items.length" class="state state--empty">
    <v-icon icon="mdi-folder-open-outline" size="40"></v-icon>
    <p class="state__title">Nothing here yet</p>
    <p class="state__sub">No {{ currentCategory.toLowerCase() }} to show at this level.</p>
  </div>

  <!-- Grid -->
  <div v-else class="grid">
    <template v-if="currentCategory === 'Assays'">
      <AssayCard
        v-for="item in items"
        :key="item.seekId"
        :data="item"
        :is-clinician-view="isClinicianView"
      />
    </template>
    <template v-else>
      <LevelCard
        v-for="item in items"
        :key="item.seekId"
        :data="item"
        drillable
        @explore="$emit('explore', $event)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { DashboardCategory } from "@/models/types";
import LevelCard from "./LevelCard.vue";
import AssayCard from "./AssayCard.vue";

defineProps<{
  items: DashboardCategory[];
  loading: boolean;
  error: string | null;
  currentCategory: string;
  isClinicianView?: boolean;
}>();

defineEmits<{
  (e: "explore", seekId: string): void;
  (e: "retry"): void;
}>();
</script>

<style scoped>
/* Fixed 3-up on desktop — wider cards fit titles better than a cramped 4-up.
   Any number of cards (the count is dynamic) simply wraps into rows of three.
   Steps down to 2 then 1 column on narrower viewports. */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: clamp(16px, 1.8vw, 22px);
}
@media (max-width: 960px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
}

/* ---- Skeleton ---- */
.skeleton {
  min-height: 184px;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.1);
  background: linear-gradient(
    100deg,
    rgba(255, 255, 255, 0.02) 30%,
    rgba(255, 255, 255, 0.05) 50%,
    rgba(255, 255, 255, 0.02) 70%
  );
  background-size: 200% 100%;
  animation: shimmer 1.3s ease-in-out infinite;
}
@keyframes shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}

/* ---- States ---- */
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: clamp(48px, 12vh, 96px) 20px;
  text-align: center;
  color: #5f7884;
}
.state__title {
  margin: 6px 0 0;
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.2rem;
  color: #e9f2f5;
}
.state__sub {
  margin: 0;
  font-size: 0.9rem;
  color: #a4bac4;
}
.state--error { color: #f0a6a6; }
.state__retry {
  margin-top: 10px;
  padding: 8px 20px;
  border-radius: 999px;
  border: 1px solid rgba(95, 214, 232, 0.4);
  background: transparent;
  color: #5fd6e8;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.3s ease;
}
.state__retry:hover { background: rgba(95, 214, 232, 0.1); }

@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; }
}
</style>
