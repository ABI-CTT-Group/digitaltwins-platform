<template>
  <div class="action-bar">
    <button
      type="button"
      class="btn btn--primary"
      :disabled="!ready || launching"
      @click.stop="$emit('launch')"
    >
      <v-progress-circular v-if="launching" indeterminate size="14" width="2" class="mr-1" />
      Launch
    </button>

    <template v-if="!isClinicianView">
      <v-tooltip text="Monitor is only available for script assays" location="top" :disabled="isScript">
        <template #activator="{ props: tip }">
          <span v-bind="tip" style="display: inline-flex">
            <button type="button" class="btn btn--secondary" :disabled="!canMonitor || !isScript" @click.stop="$emit('monitor')">
              Monitor
            </button>
          </span>
        </template>
      </v-tooltip>
      <v-tooltip text="Verify is not implemented yet" location="top">
        <template #activator="{ props: tip }">
          <span v-bind="tip" style="display: inline-flex">
            <button type="button" class="btn btn--secondary" disabled @click.stop="$emit('verify')">
              Verify
            </button>
          </span>
        </template>
      </v-tooltip>
      <button type="button" class="btn btn--secondary" :disabled="!ready || downloading" @click.stop="$emit('download')">
        <v-progress-circular v-if="downloading" indeterminate size="14" width="2" class="mr-1" />
        {{ downloading ? 'Downloading...' : 'Download' }}
      </button>
      <button type="button" class="btn btn--secondary" :disabled="!ready || submitting" @click.stop="$emit('submit')">
        <v-progress-circular v-if="submitting" indeterminate size="14" width="2" class="mr-1" />
        {{ submitting ? 'Submitting...' : 'Submit' }}
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
  /** is the assay a script type */
  isScript?: boolean;
  /** a download request in flight. */
  downloading?: boolean;
  /** a submit request in flight. */
  submitting?: boolean;
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
  transition: background 0.25s ease, border-color 0.25s ease, color 0.25s ease, opacity 0.25s ease, transform 0.2s ease;
  border: 1px solid transparent;
}
.btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

/* Primary actions: Launch, Monitor */
.btn--primary {
  color: #fff;
  background: #388e3c;
  border-color: #388e3c;
}
.btn--primary:hover:not(:disabled) {
  background: #4caf50;
  border-color: #4caf50;
  transform: translateY(-1px);
}

/* Secondary actions: Verify, Download, Submit (Legacy tonal style) */
.btn--secondary {
  color: #81c784;
  background: rgba(76, 175, 80, 0.16);
  border-color: rgba(129, 199, 132, 0.3);
}
.btn--secondary:hover:not(:disabled) {
  background: rgba(76, 175, 80, 0.3);
  border-color: rgba(129, 199, 132, 0.55);
  color: #a5d6a7;
  transform: translateY(-1px);
}
</style>
