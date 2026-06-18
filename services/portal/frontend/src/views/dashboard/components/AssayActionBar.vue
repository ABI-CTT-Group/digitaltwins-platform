<template>
  <div class="action-bar">
    <button
      type="button"
      class="btn"
      :disabled="!ready || launching"
      @click.stop="$emit('launch')"
    >
      <v-progress-circular v-if="launching" indeterminate size="14" width="2" class="mr-1" />
      Launch
    </button>

    <template v-if="!isClinicianView">
      <button type="button" class="btn" :disabled="!canMonitor" @click.stop="$emit('monitor')">
        Monitor
      </button>
      <button type="button" class="btn" :disabled="!ready" @click.stop="$emit('verify')">
        Verify
      </button>
      <button type="button" class="btn" :disabled="!ready" @click.stop="$emit('download')">
        Download
      </button>
      <button type="button" class="btn" :disabled="!ready" @click.stop="$emit('submit')">
        Submit
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  isClinicianView?: boolean;
  /** assay config saved → ready to launch / verify / download / submit. */
  ready?: boolean;
  /** launch request in flight. */
  launching?: boolean;
  /** a workflow run exists → Monitor is enabled. */
  canMonitor?: boolean;
}>();

defineEmits<{
  (e: "launch"): void;
  (e: "monitor"): void;
  (e: "verify"): void;
  (e: "download"): void;
  (e: "submit"): void;
}>();
</script>

<style scoped>
.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
/* Rectangular, softly-rounded buttons in the legacy green "tonal" style. */
.btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  padding: 7px 16px;
  border-radius: 8px;
  font-family: "Nunito", sans-serif;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  color: #81c784;
  background: rgba(76, 175, 80, 0.16);
  border: 1px solid rgba(129, 199, 132, 0.3);
  transition: background 0.25s ease, border-color 0.25s ease, color 0.25s ease, opacity 0.25s ease, transform 0.2s ease;
}
.btn:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.3);
  border-color: rgba(129, 199, 132, 0.55);
  color: #a5d6a7;
  transform: translateY(-1px);
}
.btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}
</style>
