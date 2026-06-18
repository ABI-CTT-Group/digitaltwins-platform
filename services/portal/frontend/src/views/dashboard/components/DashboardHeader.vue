<template>
  <header class="dash-header">
    <!-- Breadcrumb trail -->
    <nav class="crumbs" aria-label="Breadcrumb">
      <button type="button" class="crumb" :class="{ 'is-current': !breadcrumbs.length }" @click="$emit('go-root')">
        {{ rootLabel }}
      </button>
      <template v-for="(crumb, i) in breadcrumbs" :key="crumb.seekId">
        <v-icon class="crumbs__sep" icon="mdi-chevron-right" size="16"></v-icon>
        <v-tooltip :text="crumb.name" location="bottom" open-delay="250">
          <template #activator="{ props: tip }">
            <button
              type="button"
              class="crumb crumb--name"
              :class="{ 'is-current': i === breadcrumbs.length - 1 }"
              v-bind="tip"
              @click="$emit('go-depth', i + 1)"
            >
              {{ crumb.name }}
            </button>
          </template>
        </v-tooltip>
      </template>
    </nav>

    <!-- Current level title + meta -->
    <div class="dash-header__title-row">
      <h1 class="dash-header__title">{{ title }}</h1>
      <span v-if="!loading" class="dash-header__count">{{ count }} {{ count === 1 ? itemNoun : title.toLowerCase() }}</span>
    </div>
    <p class="dash-header__desc">{{ description }}</p>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { describeCategory } from "@/composables/useDashboardData";

const props = defineProps<{
  /** Display name for the root crumb, e.g. "Study dashboard". */
  rootLabel: string;
  breadcrumbs: Array<{ seekId: string; name: string; category: string }>;
  /** Category of the current level (plural, e.g. "Projects"). */
  currentCategory: string;
  count: number;
  loading: boolean;
}>();

defineEmits<{
  (e: "go-root"): void;
  (e: "go-depth", depth: number): void;
}>();

const title = computed(() => props.currentCategory);
const description = computed(() => describeCategory(props.currentCategory));
const itemNoun = computed(() => {
  const c = props.currentCategory;
  if (c === "Studies") return "study";
  return c.endsWith("s") ? c.slice(0, -1).toLowerCase() : c.toLowerCase();
});
</script>

<style scoped>
.dash-header {
  margin-bottom: clamp(22px, 4vh, 40px);
}

/* ---- Breadcrumbs ---- */
.crumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 18px;
}
.crumb {
  appearance: none;
  border: none;
  background: none;
  padding: 2px 4px;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #5f7884;
  cursor: pointer;
  transition: color 0.25s ease;
}
.crumb:hover { color: #5fd6e8; }
.crumb.is-current {
  color: #e9f2f5;
  cursor: default;
}
/* Keep a long item name from blowing out the breadcrumb row. */
.crumb--name {
  max-width: 26ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crumbs__sep { color: #3a4f5a; }

/* ---- Title ---- */
.dash-header__title-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}
.dash-header__title {
  margin: 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(2rem, 4.4vw, 3.1rem);
  line-height: 1.02;
  letter-spacing: -0.015em;
  color: #fff;
}
.dash-header__count {
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5fd6e8;
  opacity: 0.85;
}
.dash-header__desc {
  margin: 14px 0 0;
  max-width: 64ch;
  font-size: clamp(0.92rem, 1.3vw, 1.04rem);
  line-height: 1.55;
  color: #a4bac4;
}
</style>
