<template>
  <aside class="panel" aria-label="Case review" data-test="review-panel">
    <p v-if="!item" class="dim">Pick a case from the list to review it.</p>
    <template v-else>
      <div class="panel__head">
        <h2>{{ item.id }}</h2>
        <StatusPill :status="item.status" />
      </div>
      <p v-if="batchPos" class="batch-pos">Case {{ batchPos }} of {{ batchTotal }} in this batch</p>

      <dl class="facts">
        <dt>Scan</dt><dd>{{ item.scan }}, {{ item.slices }} slices</dd>
        <dt>Annotated by</dt><dd>{{ item.annotatedBy }}</dd>
        <template v-if="item.reviewedBy"><dt>Reviewed by</dt><dd>{{ item.reviewedBy }}</dd></template>
      </dl>
      <p v-if="item.note" class="note"><b>Correction note.</b> {{ item.note }}</p>

      <form v-if="flagging" class="flag-form" data-test="flag-form" @submit.prevent="sendForCorrection">
        <label for="flag-note">What needs correcting?</label>
        <textarea
          id="flag-note"
          ref="noteInput"
          v-model="note"
          placeholder="For example: contour misses the lower margin on slices 52 to 58"
        />
        <div class="flag-form__row">
          <button type="button" class="aurora-btn aurora-btn--ghost" @click="flagging = false">Cancel</button>
          <button type="submit" class="aurora-btn aurora-btn--solid needs">Send for correction</button>
        </div>
      </form>
      <div v-else class="actions">
        <button type="button" class="aurora-btn wide" data-test="open" @click="$emit('open')">Open in annotator</button>
        <button type="button" class="aurora-btn aurora-btn--solid ok" data-test="confirm" @click="$emit('decide', 'confirmed', null)">
          Confirm annotation
        </button>
        <button type="button" class="aurora-btn needs" data-test="flag" @click="startFlag">Needs correction</button>
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { useToast } from "vue-toastification";
import type { Case } from "../model/worklist";
import StatusPill from "./StatusPill.vue";

const props = defineProps<{ item: Case | null; batchPos: number; batchTotal: number }>();
const emit = defineEmits<{ decide: ["confirmed" | "needs", string | null]; open: [] }>();

const toast = useToast();
const flagging = ref(false);
const note = ref("");
const noteInput = ref<HTMLTextAreaElement | null>(null);

// A different case starts with the decision buttons, not a half-written note.
watch(() => props.item?.id, () => { flagging.value = false; note.value = ""; });

async function startFlag() {
  flagging.value = true;
  await nextTick();
  noteInput.value?.focus();
}

function sendForCorrection() {
  const text = note.value.trim();
  if (!text) {
    toast.warning("Add a note so the annotator knows what to fix.");
    noteInput.value?.focus();
    return;
  }
  emit("decide", "needs", text);
}
</script>

<style scoped>
.panel {
  position: sticky; top: 16px; display: grid; gap: 16px; padding: 20px;
  background: rgba(8, 22, 31, 0.72); border: 1px solid var(--line); border-radius: 12px;
}
.panel__head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
h2 { margin: 0; font-family: var(--font-title); font-weight: 400; font-size: 1.6rem; color: var(--text); }
.batch-pos { margin: -10px 0 0; font-size: 0.875rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }
.dim { margin: 0; color: var(--text-dim); }
.facts { display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; margin: 0; font-size: 0.9rem; }
.facts dt { color: var(--text-faint); }
.facts dd { margin: 0; }
.note { margin: 0; padding: 4px 0 4px 12px; border-left: 2px solid var(--tone-needs); font-size: 0.9rem; color: var(--text-dim); }
.note b { color: var(--text); font-weight: 600; }

.actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.actions .wide { grid-column: 1 / -1; }
.ok { --accent: var(--accent-measurements); }
.needs { --accent: var(--tone-needs); }

.flag-form { display: grid; gap: 8px; }
.flag-form label { font-size: 0.875rem; color: var(--text-dim); }
.flag-form textarea {
  min-height: 72px; padding: 8px 10px; resize: vertical; font-size: 0.9rem; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--line); color: var(--text);
}
.flag-form__row { display: flex; justify-content: flex-end; gap: 8px; }

@media (max-width: 960px) { .panel { position: static; } }
@media (max-width: 480px) { .actions { grid-template-columns: 1fr; } }
</style>
