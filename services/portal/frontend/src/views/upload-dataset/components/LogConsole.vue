<template>
  <v-dialog v-model="open" max-width="980" transition="dialog-bottom-transition" @keydown.esc="close">
    <v-card rounded="lg" flat class="overflow-hidden log-console-card">
      <!-- Glass header — backdrop-filter only on the static header, not on scrolling content -->
      <div class="log-header d-flex align-center px-5 py-3 gap-3">
        <span class="log-header__title text-body-1 font-weight-medium">
          {{ kind === 'build' ? 'Build' : 'Deploy' }} &middot; {{ title }}
        </span>

        <v-chip
          size="small"
          :color="statusColor"
          variant="tonal"
          class="text-caption font-weight-bold log-header__status"
        >
          {{ status }}
        </v-chip>

        <span class="log-header__timer text-caption font-weight-medium ml-1">
          &#9203; {{ elapsed }}
        </span>

        <v-spacer />

        <v-btn
          icon
          size="small"
          variant="text"
          color="#9fb4bf"
          title="Copy all"
          @click="copyAll"
        >
          <v-icon size="18">mdi-content-copy</v-icon>
        </v-btn>

        <v-btn
          icon
          size="small"
          variant="text"
          color="#9fb4bf"
          title="Close"
          @click="close"
        >
          <v-icon size="18">mdi-close</v-icon>
        </v-btn>
      </div>

      <v-divider style="border-color: rgba(120,200,220,0.12);" />

      <!-- Log body: plain overflow:auto — no backdrop-filter, no animation, no nested scroll -->
      <div ref="scroller" class="log-body">
        <div v-if="lines.length === 0" class="log-body__empty">
          Waiting for output&hellip;
        </div>
        <div
          v-for="(line, i) in lines"
          :key="i"
          class="log-body__line"
        >{{ line }}</div>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import { streamLogs } from '@/bootstrap/tool_api';

const props = defineProps<{
  modelValue: boolean;
  kind: 'build' | 'deploy';
  jobId: string;
  title: string;
  startedAt: string;
  /** Finish time — present only for an already-finished job; makes the timer
   *  show the frozen duration (end - start) instead of "time since". */
  endedAt?: string;
  initialStatus: string;
}>();

const emit = defineEmits(['update:modelValue']);

// v-model binding
const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const lines = ref<string[]>([]);
const status = ref(props.initialStatus);
const elapsed = ref('00:00');
let ctrl: AbortController | null = null;
let timer: number | undefined;
const scroller = ref<HTMLElement>();

// Status badge colour
const statusColor = computed(() => {
  switch (status.value) {
    case 'completed': return '#5fd6e8';
    case 'failed':    return '#ff6b6b';
    case 'building':
    case 'deploying': return '#f0c040';
    default:          return '#9fb4bf';
  }
});

// Elapsed timer — computed from startedAt ISO prop, not stream duration
function fmt(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

// Parse a start timestamp robustly. Backend DB timestamps (createdAt/updatedAt)
// are serialized WITHOUT a timezone designator but are actually UTC; a bare
// `new Date('2026-06-20T21:00:00')` would parse them as LOCAL time, throwing the
// elapsed timer off by the viewer's UTC offset (e.g. +12h in Auckland). Treat
// tz-less strings as UTC by appending 'Z'.
function parseStart(s: string): number {
  if (!s) return Date.now();
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(s.trim());
  const t = new Date(hasTz ? s : `${s}Z`).getTime();
  return Number.isNaN(t) ? Date.now() : t;
}

const isActive = (s: string) =>
  s === 'building' || s === 'deploying' || s === 'pending';

// Set the displayed elapsed value. For a finished job opened with a known end
// time, show the frozen DURATION (end - start). Otherwise show wall-clock time
// since start (live).
function refreshElapsed() {
  const t0 = parseStart(props.startedAt);
  if (!isActive(status.value) && props.endedAt) {
    elapsed.value = fmt(parseStart(props.endedAt) - t0);
  } else {
    elapsed.value = fmt(Date.now() - t0);
  }
}

function startTimer() {
  // Reopened on an already-finished job → duration is fixed, no ticking.
  if (!isActive(status.value)) {
    refreshElapsed();
    return;
  }
  timer = window.setInterval(() => {
    if (isActive(status.value)) refreshElapsed();
  }, 1000);
}

function autoscroll() {
  requestAnimationFrame(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
  });
}

function connect() {
  lines.value = [];
  ctrl = streamLogs(
    props.kind,
    props.jobId,
    (l) => { lines.value.push(l); autoscroll(); },
    (s) => { status.value = s; clearInterval(timer); },
    (e) => { lines.value.push(`[stream error] ${String(e)}`); },
  );
}

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    status.value = props.initialStatus;
    refreshElapsed();
    connect();
    startTimer();
  } else {
    ctrl?.abort();
    ctrl = null;
    clearInterval(timer);
  }
});

function copyAll() {
  navigator.clipboard?.writeText(lines.value.join('\n'));
}

function close() {
  emit('update:modelValue', false);
}

onBeforeUnmount(() => {
  ctrl?.abort();
  clearInterval(timer);
});
</script>

<style scoped>
.log-console-card {
  background: #0a141b !important;
  border: 1px solid rgba(120, 200, 220, 0.18);
  color: #c3d2d8;
  display: flex;
  flex-direction: column;
}

/* Glass header — static, not scrolling; backdrop-filter is safe here */
.log-header {
  background: rgba(8, 18, 26, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(120, 200, 220, 0.10);
  flex-shrink: 0;
}

.log-header__title {
  color: #e9f2f5;
  font-family: 'Fraunces', Georgia, serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 340px;
}

.log-header__timer {
  color: #9fb4bf;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  white-space: nowrap;
}

.log-header__status {
  white-space: nowrap;
}

/* Log body: single plain overflow:auto region.
   NO backdrop-filter, NO animation, NO mask on this element (aurora constraint). */
.log-body {
  background: #0a141b;
  font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.8125rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  max-height: 60vh;
  min-height: 200px;
  padding: 16px 20px;
  color: #c3d2d8;
  flex: 1 1 auto;
}

.log-body__line {
  margin: 0;
  padding: 0;
}

.log-body__empty {
  color: #5f7a85;
  font-style: italic;
}

/* Scrollbar styling — dark theme */
.log-body::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.log-body::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
}
.log-body::-webkit-scrollbar-thumb {
  background: rgba(120, 200, 220, 0.25);
  border-radius: 3px;
}
.log-body::-webkit-scrollbar-thumb:hover {
  background: rgba(120, 200, 220, 0.45);
}
</style>
