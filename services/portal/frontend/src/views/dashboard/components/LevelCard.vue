<template>
  <component
    :is="drillable ? 'button' : 'div'"
    class="level-card"
    :class="{ 'is-static': !drillable }"
    :type="drillable ? 'button' : undefined"
    @click="drillable ? $emit('explore', data.seekId) : undefined"
  >
    <span class="level-card__rail" aria-hidden="true"></span>

    <span class="level-card__top">
      <span class="level-card__kind">{{ singular }}</span>
      <span v-if="data.tag" class="level-card__tag">{{ data.tag }}</span>
    </span>

    <v-tooltip :text="data.name" location="top" open-delay="250">
      <template #activator="{ props: tip }">
        <span class="level-card__name" v-bind="tip">{{ data.name }}</span>
      </template>
    </v-tooltip>
    <span v-if="data.description" class="level-card__desc">{{ data.description }}</span>

    <span v-if="drillable" class="level-card__cta">
      <span>Explore</span>
      <v-icon icon="mdi-arrow-right" size="18"></v-icon>
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { DashboardCategory } from "@/models/types";

const props = defineProps<{
  data: DashboardCategory;
  /** When false the card is a plain tile with no drill affordance. */
  drillable?: boolean;
}>();

defineEmits<{ (e: "explore", seekId: string): void }>();

/** "Studies" → "Study", "Programmes" → "Programme", etc. */
const singular = computed(() => {
  const c = props.data.category;
  if (c === "Studies") return "Study";
  return c.endsWith("s") ? c.slice(0, -1) : c;
});
</script>

<style scoped>
.level-card {
  --accent: #5fd6e8;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-height: 184px;
  padding: 22px 22px 20px;
  text-align: left;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: rgba(255, 255, 255, 0.028);
  color: inherit;
  font-family: "Nunito", sans-serif;
  overflow: hidden;
  appearance: none;
  cursor: pointer;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s ease, background 0.4s ease;
}
.level-card.is-static {
  cursor: default;
}

.level-card__rail {
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.level-card:not(.is-static):hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: rgba(255, 255, 255, 0.045);
}
.level-card:not(.is-static):hover .level-card__rail {
  transform: scaleX(1);
}

.level-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.level-card__kind {
  font-size: 0.66rem;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--accent);
  opacity: 0.85;
}
.level-card__tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #a4bac4;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(120, 200, 220, 0.14);
}
.level-card__name {
  font-size: 1.22rem;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.01em;
  color: #fff;
  /* Clamp long names to 2 lines + ellipsis; full text via native title tooltip. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.level-card__desc {
  flex: 1;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #a4bac4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.level-card__cta {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  gap: 7px;
  margin-top: auto;
  padding: 7px 18px;
  border-radius: 8px;
  font-size: 0.84rem;
  font-weight: 700;
  /* pink-darken-2 tonal — matches the legacy Explore button */
  color: #f06292;
  background: rgba(194, 24, 91, 0.16);
  border: 1px solid rgba(240, 98, 146, 0.28);
  transition: background 0.3s ease, border-color 0.3s ease;
}
.level-card:not(.is-static):hover .level-card__cta {
  background: rgba(194, 24, 91, 0.28);
  border-color: rgba(240, 98, 146, 0.5);
}
.level-card__cta .v-icon {
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}
.level-card:not(.is-static):hover .level-card__cta .v-icon {
  transform: translateX(4px);
}
</style>
