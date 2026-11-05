<template>
  <v-dialog v-model="open" max-width="560" transition="dialog-bottom-transition">
    <v-card rounded="lg" flat class="approve">
      <h2 class="approve__title">{{ title }}</h2>

      <!-- Confirm -->
      <template v-if="phase === 'confirm'">
        <p class="approve__text">{{ APPROVE_INTRO[category] }}</p>
        <v-select
          v-if="adapter.needsProject"
          v-model="seekProjectId"
          :items="projects"
          item-title="title"
          item-value="id"
          label="SEEK project"
          variant="outlined"
          density="comfortable"
          color="#5fd6e8"
          :loading="loadingProjects"
          :error-messages="projectsError"
          prepend-inner-icon="mdi-folder-account-outline"
        />
        <p v-if="hint" class="approve__hint">{{ hint }}</p>
        <p v-if="startError" class="step-error" role="alert">
          <v-icon icon="mdi-alert-circle-outline" size="18" /> {{ startError }}
        </p>
      </template>

      <!-- Progress -->
      <template v-else-if="phase === 'progress'">
        <p class="approve__stage" :class="{ 'is-waiting': progress?.state === 'waiting' }">{{ progress?.stage }}</p>
        <v-progress-linear
          :model-value="progress?.percent ?? 0"
          :indeterminate="progress?.percent === undefined"
          :color="progress?.state === 'waiting' ? 'var(--tone-needs)' : '#5fd6e8'"
          rounded
          height="6"
        />
        <p class="approve__text">You can close this: the {{ noun }}'s card keeps following it.</p>
      </template>

      <!-- Done or failed -->
      <template v-else>
        <template v-if="progress?.state === 'done'">
          <p class="approve__result">{{ item?.name }} is in the platform.</p>
          <p v-if="progress.fhirError" class="approve__hint is-failed">
            FHIR publishing failed: {{ progress.fhirError }}. Retry it from the card.
          </p>
        </template>
        <template v-else>
          <p class="approve__result is-failed">Approval failed</p>
          <p v-if="progress?.error" class="approve__text">{{ progress.error }}</p>
          <p class="approve__text">Nothing was added to the platform. Approve it again from its card.</p>
        </template>
      </template>

      <div class="approve__actions">
        <button type="button" class="aurora-btn aurora-btn--ghost" :disabled="starting" @click="close">
          {{ phase === 'confirm' ? 'Cancel' : 'Close' }}
        </button>
        <button
          v-if="phase === 'confirm'"
          type="button"
          class="aurora-btn aurora-btn--solid"
          :disabled="starting || (adapter.needsProject && !seekProjectId)"
          @click="approve"
        >
          <v-progress-circular v-if="starting" indeterminate size="14" width="2" />
          Approve
        </button>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * The one Approve dialog for the four hubs: confirm (a SEEK project for tools and workflows, and a line about FHIR
 * when there's no annotation), then live progress, then the outcome. Closing it mid-way doesn't cancel anything:
 * the card keeps following the approval.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { SeekProject } from '@/models/types';
import { useSeekProjects } from '@/bootstrap/tool_api';
import { APPROVE_INTRO, approveAdapter, fhirHint, type ApprovalProgress, type ApproveCategory } from './approveAdapters';
import { describeApiError } from './apiError';

type Item = { id: string; name: string; hasAnnotation?: boolean; seekProjectId?: number };
const props = defineProps<{ category: ApproveCategory; item: Item | null }>();
const open = defineModel<boolean>({ default: false });
/** The approval started and the dialog closed, or it reached its end: the hub refreshes its list. */
const emit = defineEmits<{ (e: 'finished', progress: ApprovalProgress | null): void }>();

const POLL_MS = 2000;
const NOUNS: Record<ApproveCategory, string> = { tools: 'tool', workflows: 'workflow', measurements: 'dataset', models: 'model' };

const adapter = computed(() => approveAdapter(props.category));
const noun = computed(() => NOUNS[props.category]);
const hint = computed(() => (props.item ? fhirHint(props.category, props.item) : undefined));

const phase = ref<'confirm' | 'progress' | 'result'>('confirm');
const title = computed(() => {
  const name = props.item?.name ?? '';
  if (phase.value === 'confirm') return `Approve ${name}?`;
  return phase.value === 'progress' ? `Approving ${name}` : name;
});
const progress = ref<ApprovalProgress | null>(null);
const projects = ref<SeekProject[]>([]);
const loadingProjects = ref(false);
const projectsError = ref('');
const seekProjectId = ref<number | undefined>();
const starting = ref(false);
const startError = ref('');
let timer: ReturnType<typeof setTimeout> | undefined;

const stop = () => { if (timer) clearTimeout(timer); timer = undefined; };

watch(open, async (isOpen) => {
  stop();
  if (!isOpen) return;
  phase.value = 'confirm';
  progress.value = null;
  startError.value = '';
  seekProjectId.value = props.item?.seekProjectId;  // the previous approval's project
  if (!adapter.value.needsProject) return;
  loadingProjects.value = true;
  projectsError.value = '';
  try {
    projects.value = await useSeekProjects();
  } catch (err) {
    projectsError.value = describeApiError(err, 'Loading the SEEK projects');
  } finally {
    loadingProjects.value = false;
  }
});

function show(next: ApprovalProgress) {
  progress.value = next;
  if (next.state === 'done' || next.state === 'failed') {
    phase.value = 'result';
    emit('finished', next);
    return;
  }
  phase.value = 'progress';
  timer = setTimeout(poll, POLL_MS);
}

async function approve() {
  if (!props.item) return;
  starting.value = true;
  startError.value = '';
  try {
    show(await adapter.value.start(props.item, seekProjectId.value));
  } catch (err) {
    startError.value = describeApiError(err, 'Approval');
  } finally {
    starting.value = false;
  }
}

async function poll() {
  if (!props.item || !open.value) return;
  try {
    show(await adapter.value.poll(props.item));
  } catch (err) {
    console.warn('Approval status poll failed:', err);
    timer = setTimeout(poll, POLL_MS);  // a missed poll isn't the approval failing
  }
}

function close() {
  const midway = phase.value === 'progress';
  stop();
  open.value = false;
  if (midway) emit('finished', progress.value);
}

onBeforeUnmount(stop);
</script>

<style scoped>
.approve {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px;
  background: var(--ink) !important;
  border: 1px solid var(--line);
  color: var(--text);
  font-family: var(--font-ui);
}
.approve__title { margin: 0; font-family: var(--font-title); font-weight: 500; font-size: 1.44rem; color: var(--text); overflow-wrap: anywhere; }
.approve__text { margin: 0; max-width: 60ch; font-size: 0.9375rem; line-height: 1.55; color: var(--text-dim); }
.approve__hint { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--tone-needs); }
.approve__hint.is-failed, .approve__result.is-failed { color: var(--tone-failed); }
.approve__stage { margin: 0; font-size: 1rem; font-weight: 600; color: var(--text); }
.approve__stage.is-waiting { color: var(--tone-needs); }
.approve__result { margin: 0; font-size: 1.2rem; font-weight: 600; color: var(--text); }
.approve__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }
</style>
