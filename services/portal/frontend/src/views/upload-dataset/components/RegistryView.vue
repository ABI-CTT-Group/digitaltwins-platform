<template>
  <v-container class="d-flex align-center justify-center">
    <v-card
      class="pa-6 responsive-box d-flex flex-column align-center justify-center aurora-panel"
      flat
    >
      <!-- Register button -->
      <div class="w-100 d-flex justify-start">
        <button
          type="button"
          class="aurora-btn register-btn my-2"
          :style="{ '--accent': accent }"
          :disabled="disabled"
          @click="emit('register')"
        >
          <v-icon icon="mdi-plus-circle-outline" size="18" />
          {{ registerLabel }}
        </button>
      </div>

      <!-- List panel -->
      <div class="d-flex flex-column w-100 my-2 pa-5 rounded registry-container">
        <Search :label="searchLabel" v-model:search="search" @search="handleSearch" :accent="accent" />
        <Refresh @refresh="handleRefresh" />
        <div class="d-flex flex-grow-1">
          <div v-if="displayItems.length > 0" class="ucard-grid pa-5">
            <slot :items="displayItems" />
          </div>
          <NoData v-else />
        </div>
      </div>
    </v-card>
  </v-container>
</template>

<script setup lang="ts" generic="T extends { id: string; status?: string }">
import { ref, watch, onBeforeMount, onUnmounted } from 'vue';
import Fuse from 'fuse.js';
import Search from './Search.vue';
import Refresh from './Refresh.vue';
import NoData from './NoData.vue';

// ---- props / emits --------------------------------------------------------
const props = withDefaults(
  defineProps<{
    /** Function to fetch the full list */
    fetchList: () => Promise<T[]>;
    /** Label for the register button */
    registerLabel?: string;
    /** Placeholder for the search field */
    searchLabel?: string;
    /** Whether the register button is disabled */
    disabled?: boolean;
    /** Per-page identity accent (hex) for the register button + search. */
    accent?: string;
    /** Auto-poll interval in milliseconds; 0 = disabled */
    pollInterval?: number;
    /** Predicate to determine if any item is in a "pending" state that requires polling */
    isPending?: (items: T[]) => boolean;
  }>(),
  {
    registerLabel: 'Register a new item',
    searchLabel: 'Search',
    disabled: false,
    accent: '#5fd6e8',
    pollInterval: 5000,
    isPending: (items: T[]) => false,
  },
);

const emit = defineEmits<{
  (e: 'register'): void;
  (e: 'refresh', items: T[]): void;
}>();

// ---- state ----------------------------------------------------------------
const allItems = ref<T[]>([]) as { value: T[] };
const displayItems = ref<T[]>([]) as { value: T[] };
const search = ref('');
const isStatusPending = ref(false);
let refreshInterval: number | undefined;

// ---- refresh / search -----------------------------------------------------
const handleRefresh = async () => {
  const items = await props.fetchList();
  allItems.value = items;
  displayItems.value = items;
  isStatusPending.value = props.isPending(items);
  emit('refresh', items);
};

const handleSearch = () => {
  if (!search.value) { displayItems.value = allItems.value; return; }
  const fuse = new Fuse(allItems.value, { keys: ['name'], threshold: 0.4 });
  displayItems.value = fuse.search(search.value).map((r) => r.item);
};

watch(search, (val) => { if (!val) displayItems.value = allItems.value; });

// ---- auto-polling ---------------------------------------------------------
watch(isStatusPending, (pending) => {
  if (pending && !refreshInterval && props.pollInterval > 0) {
    refreshInterval = window.setInterval(() => {
      handleRefresh().catch((err) => console.error('Registry refresh failed:', err));
    }, props.pollInterval);
  } else if (!pending && refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = undefined;
  }
}, { immediate: true });

onBeforeMount(handleRefresh);
onUnmounted(() => { if (refreshInterval) clearInterval(refreshInterval); });

// expose for parent to trigger refresh programmatically
defineExpose({ handleRefresh });
</script>

<style scoped>
.responsive-box { width: 90% !important; }
@media (min-width: 2100px) {
  .responsive-box { width: 75% !important; }
}
.aurora-panel {
  background: rgba(8, 18, 26, 0.55) !important;
  border: 1px solid rgba(120, 200, 220, 0.16);
  border-radius: 20px !important;
}
.registry-container {
  min-height: 50vh;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: rgba(255, 255, 255, 0.015);
}
/* Deep, muted accent fill — a calm CTA rather than the bright solid button. */
.register-btn {
  padding: 10px 20px;
  font-size: 0.9rem;
  white-space: nowrap;
  background: color-mix(in srgb, var(--accent) 20%, rgba(7, 19, 27, 0.92)) !important;
  border: 1px solid color-mix(in srgb, var(--accent) 38%, transparent) !important;
  color: color-mix(in srgb, var(--accent) 86%, #ffffff) !important;
  box-shadow: none !important;
}
.register-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 30%, rgba(7, 19, 27, 0.92)) !important;
  border-color: color-mix(in srgb, var(--accent) 58%, transparent) !important;
  color: #ffffff !important;
  transform: translateY(-1px);
}
/* Elastic card grid — cards flex to fill the row and wrap; a lone card stays a
   sensible width (left-aligned) rather than stretching across the panel.
   align-self/align-content keep the grid (a flex item in a tall flex-grow
   parent) from stretching vertically — otherwise the single row of cards
   stretches to fill the panel height on tall/ultra-wide screens. */
.ucard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: clamp(16px, 1.6vw, 22px);
  width: 100%;
  align-self: flex-start;
  align-content: flex-start;
}
</style>
