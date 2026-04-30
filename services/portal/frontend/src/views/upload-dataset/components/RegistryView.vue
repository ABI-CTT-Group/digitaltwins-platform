<template>
  <v-container class="d-flex align-center justify-center">
    <v-card
      class="pa-6 responsive-box d-flex flex-column align-center justify-center"
      elevation="12"
      style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
    >
      <!-- Register button -->
      <div class="w-100 d-flex justify-start">
        <v-btn
          color="pink"
          :text="registerLabel"
          variant="tonal"
          :width="350"
          rounded="md"
          prepend-icon="mdi-plus-circle-outline"
          class="hover-animate my-2"
          :disabled="disabled"
          @click="emit('register')"
        />
      </div>

      <!-- List panel -->
      <div class="d-flex flex-column w-100 my-2 pa-5 border-sm rounded registry-container">
        <Search :label="searchLabel" v-model:search="search" @on:search="handleSearch" />
        <Refresh @on:refresh="handleRefresh" />
        <div class="d-flex flex-grow-1">
          <div v-if="displayItems.length > 0" class="d-flex flex-wrap ga-10 pa-5 justify-start">
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
    /** Auto-poll interval in milliseconds; 0 = disabled */
    pollInterval?: number;
    /** Predicate to determine if any item is in a "pending" state that requires polling */
    isPending?: (items: T[]) => boolean;
  }>(),
  {
    registerLabel: 'Register a new item',
    searchLabel: 'Search',
    disabled: false,
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
.registry-container { min-height: 50vh; }
</style>
