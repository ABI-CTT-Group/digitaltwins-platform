<template>
  <div class="registry" :style="{ '--accent': accent }">
    <div class="registry__bar">
      <button
        type="button"
        class="aurora-btn aurora-btn--solid registry__register"
        :style="{ '--accent': accent }"
        :disabled="disabled"
        @click="emit('register')"
      >
        <v-icon icon="mdi-plus" size="18" />
        {{ registerLabel }}
      </button>
      <!-- Optional extra filters (e.g. a status dropdown), narrowing on top of the search box -->
      <div v-if="$slots.filters" class="registry__filters">
        <slot name="filters" />
      </div>
      <div class="registry__tools">
        <v-text-field
          v-model="search"
          :label="searchLabel"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          :base-color="'var(--text-faint)'"
          :color="accent"
          clearable
          hide-details
          class="registry__search"
        />
        <button
          type="button"
          class="aurora-btn aurora-btn--ghost aurora-btn--sm"
          :disabled="phase === 'loading'"
          @click="load"
        >
          <v-icon icon="mdi-refresh" size="16" /> Refresh
        </button>
      </div>
    </div>

    <p v-if="pollFailed && phase === 'ready'" class="registry__notice" role="status">
      <v-icon icon="mdi-cloud-off-outline" size="16" />
      Couldn't refresh. Showing the list as it was a moment ago.
    </p>

    <div v-if="phase === 'loading'" class="registry__grid" role="status" aria-label="Loading">
      <span class="registry__loading">Loading…</span>
      <div v-for="n in 3" :key="n" class="registry__skeleton" aria-hidden="true" />
    </div>

    <div v-else-if="phase === 'error'" class="registry__state" role="alert">
      <h2 class="registry__state-title">Couldn't load the list</h2>
      <p class="registry__state-text">{{ loadError }}</p>
      <button type="button" class="aurora-btn" @click="load">Try again</button>
    </div>

    <div v-else-if="allItems.length === 0" class="registry__state">
      <slot name="empty">
        <p class="registry__state-text">Nothing registered yet.</p>
      </slot>
    </div>

    <div v-else-if="displayItems.length === 0" class="registry__state">
      <p class="registry__state-text">Nothing matches your search or filter.</p>
    </div>

    <div v-else class="registry__grid">
      <slot :items="displayItems" />
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends { id: string; status?: string }">
import { ref, watch, onBeforeMount, onUnmounted } from 'vue';
import type { Ref } from 'vue';
import Fuse from 'fuse.js';
import { getApiErrorMessage } from '@/utils/common';

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
    /** The hub's category accent for the register button and search focus. */
    accent?: string;
    /** Auto-poll interval in milliseconds; 0 = disabled */
    pollInterval?: number;
    /** Predicate to determine if any item is in a "pending" state that requires polling */
    isPending?: (items: T[]) => boolean;
    /** Optional predicate (e.g. a status filter) applied on top of the search box.
     *  Pass a computed so a new reference flows through whenever the filter changes. */
    filterFn?: (item: T) => boolean;
  }>(),
  {
    registerLabel: 'Register a new item',
    searchLabel: 'Search',
    disabled: false,
    accent: 'var(--accent-tools)',
    pollInterval: 5000,
    isPending: () => false,
    filterFn: undefined,
  },
);

const emit = defineEmits<{
  (e: 'register'): void;
  (e: 'refresh', items: T[]): void;
}>();

// ---- state ----------------------------------------------------------------
// loading: the first fetch (or a retry after an error) is under way; error: it failed and there is
// no list to show; ready: a list is shown. A failed poll keeps the last list and sets pollFailed.
const phase = ref<'loading' | 'error' | 'ready'>('loading');
const loadError = ref('');
const pollFailed = ref(false);
const allItems = ref<T[]>([]) as Ref<T[]>;
const displayItems = ref<T[]>([]) as Ref<T[]>;
const search = ref<string | null>('');
const isStatusPending = ref(false);
let refreshInterval: number | undefined;

// ---- refresh / search -----------------------------------------------------
const applyDisplay = () => {
  const base = props.filterFn ? allItems.value.filter(props.filterFn) : allItems.value;
  if (!search.value) { displayItems.value = base; return; }
  const fuse = new Fuse(base, { keys: ['name'], threshold: 0.4 });
  displayItems.value = fuse.search(search.value).map((r) => r.item);
};

const handleRefresh = async () => {
  const items = await props.fetchList();
  allItems.value = items;
  applyDisplay();
  isStatusPending.value = props.isPending(items);
  pollFailed.value = false;
  phase.value = 'ready';
  emit('refresh', items);
};

/** A fetch the user asked for (first load, Refresh, Try again): a failure with no list shows the error. */
const load = async () => {
  if (phase.value !== 'ready') phase.value = 'loading';
  try {
    await handleRefresh();
  } catch (err) {
    console.error('Registry load failed:', err);
    if (phase.value === 'ready') {
      pollFailed.value = true;
    } else {
      loadError.value = getApiErrorMessage(err, 'Loading');
      phase.value = 'error';
    }
  }
};

watch(search, () => applyDisplay());
watch(() => props.filterFn, () => applyDisplay());

// ---- auto-polling ---------------------------------------------------------
watch(isStatusPending, (pending) => {
  if (pending && !refreshInterval && props.pollInterval > 0) {
    refreshInterval = window.setInterval(() => {
      handleRefresh().catch((err) => {
        console.error('Registry refresh failed:', err);
        pollFailed.value = true;
      });
    }, props.pollInterval);
  } else if (!pending && refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = undefined;
  }
}, { immediate: true });

onBeforeMount(load);
onUnmounted(() => { if (refreshInterval) clearInterval(refreshInterval); });

// expose for parent to trigger refresh programmatically
defineExpose({ handleRefresh: load });
</script>

<style scoped>
.registry { font-family: var(--font-ui); color: var(--text); }

.registry__bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  margin-bottom: 20px;
}
.registry__register { padding: 10px 18px; font-size: 0.9375rem; }
.registry__filters { display: flex; align-items: center; gap: 8px; }
/* Right-aligned on wide screens; when the bar wraps (phones) it takes the full row. */
.registry__tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 300px;
  max-width: 440px;
  margin-left: auto;
}
.registry__search { flex: 1; min-width: 0; }
.registry__search :deep(.v-field__input) { color: var(--text); caret-color: var(--text); }

.registry__notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  font-size: 0.875rem;
  color: var(--tone-needs);
}

/* Elastic card grid — cards flex to fill the row and wrap; a lone card stays a sensible width. */
.registry__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: clamp(14px, 1.6vw, 20px);
}
.registry__loading {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.registry__skeleton {
  min-height: 188px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: linear-gradient(100deg, var(--surface) 30%, rgba(255, 255, 255, 0.06) 50%, var(--surface) 70%);
  background-size: 300% 100%;
  animation: registry-shimmer 1.6s ease-in-out infinite;
}
@keyframes registry-shimmer { from { background-position: 100% 0; } to { background-position: 0 0; } }
@media (prefers-reduced-motion: reduce) {
  .registry__skeleton { animation: none; }
}

.registry__state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 40px 0;
  max-width: 60ch;
}
.registry__state-title { margin: 0; font-size: 1.2rem; font-weight: 600; color: var(--text); }
.registry__state-text { margin: 0; font-size: 1rem; line-height: 1.55; color: var(--text-dim); }
</style>
