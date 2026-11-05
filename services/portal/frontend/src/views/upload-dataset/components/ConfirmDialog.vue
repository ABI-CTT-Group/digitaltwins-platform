<template>
  <v-dialog v-model="open" max-width="480" :persistent="busy">
    <div class="confirm" role="alertdialog" :aria-label="title">
      <h2 class="confirm__title">{{ title }}</h2>
      <p class="confirm__text">{{ text }}</p>
      <p v-if="error" class="confirm__error" role="alert">
        <v-icon icon="mdi-alert-circle-outline" size="16" /> {{ error }}
      </p>
      <div class="confirm__actions">
        <button type="button" class="aurora-btn aurora-btn--ghost" :disabled="busy" @click="open = false">{{ dismissLabel }}</button>
        <button type="button" class="aurora-btn aurora-btn--solid confirm__go" :disabled="busy" @click="go">
          <v-progress-circular v-if="busy" indeterminate size="14" width="2" />
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

// Asks before a destructive hub action (delete, cancel an upload), then runs it. The dialog stays
// open with the reason if the action fails, so the user can retry or cancel.
const open = defineModel<boolean>({ default: false });
const props = withDefaults(defineProps<{
  title: string;
  text: string;
  confirmLabel: string;
  /** The button that closes without acting ("Keep it" where "Cancel" would be ambiguous). */
  dismissLabel?: string;
  action: () => Promise<unknown>;
}>(), { dismissLabel: 'Cancel' });

const busy = ref(false);
const error = ref('');

watch(open, (isOpen) => { if (isOpen) error.value = ''; });

const reason = (err: any): string => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  return err?.message || 'It didn\'t work. Try again.';
};

const go = async () => {
  busy.value = true;
  error.value = '';
  try {
    await props.action();
    open.value = false;
  } catch (err) {
    error.value = reason(err);
  } finally {
    busy.value = false;
  }
};
</script>

<style scoped>
.confirm {
  padding: 24px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--ink);
  font-family: var(--font-ui);
  color: var(--text);
}
.confirm__title { margin: 0 0 10px; font-size: 1.2rem; font-weight: 600; }
.confirm__text { margin: 0; font-size: 1rem; line-height: 1.55; color: var(--text-dim); max-width: 60ch; }
.confirm__error {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 14px 0 0;
  font-size: 0.875rem;
  color: var(--tone-failed);
}
.confirm__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; }
.confirm__go { --accent: var(--tone-failed); }
</style>
