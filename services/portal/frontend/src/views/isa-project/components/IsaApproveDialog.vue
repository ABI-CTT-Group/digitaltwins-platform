<template>
  <v-dialog v-model="open" max-width="560" transition="dialog-bottom-transition">
    <v-card rounded="lg" flat class="approve" data-test="isa-approve">
      <h2 class="approve__title">{{ title }}</h2>

      <template v-if="phase === 'confirm'">
        <p class="approve__text">
          Its SEEK project is created from the ISA tree, and its bundled datasets, workflows and tools are
          registered so any project can use them.
        </p>
        <p class="approve__text">{{ bundledLine }}</p>
        <p class="approve__hint">Prototype: nothing reaches the platform; only this browser's list changes.</p>
      </template>

      <template v-else-if="phase === 'progress'">
        <p class="approve__stage">{{ stage }}</p>
        <v-progress-linear indeterminate color="#5fd6e8" rounded height="6" />
        <p class="approve__text">You can close this: the project's row keeps following it.</p>
      </template>

      <p v-else class="approve__result">{{ name }} is in the platform.</p>

      <div class="approve__actions">
        <button type="button" class="aurora-btn aurora-btn--ghost" @click="open = false">
          {{ phase === 'confirm' ? 'Cancel' : 'Close' }}
        </button>
        <button v-if="phase === 'confirm'" type="button" class="aurora-btn aurora-btn--solid" @click="approve">
          Approve
        </button>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
// Approve an uploaded ISA project (prototype). It looks and reads like the other hubs' Approve dialog
// (upload-dataset/components/ApproveDialog.vue) but only drives the store's simulated approval.
import { computed, ref, watch } from "vue";
import { useIsaProjectStore } from "../isaProjectStore";

const props = defineProps<{ projectId: string | null }>();
const open = defineModel<boolean>({ default: false });

const store = useIsaProjectStore();
const entry = computed(() => store.entries.find(e => e.project.project.id === props.projectId) ?? null);
const name = computed(() => entry.value?.project.project.title ?? "");
const started = ref(false);

const approval = computed(() => entry.value?.approval);
const phase = computed(() =>
  !started.value && !approval.value ? "confirm" : approval.value?.state === "approving" ? "progress" : "result");
const stage = computed(() => (approval.value?.state === "approving" ? approval.value.stage : ""));
const title = computed(() =>
  phase.value === "confirm" ? `Approve ${name.value}?` : phase.value === "progress" ? `Approving ${name.value}` : name.value);

const bundledLine = computed(() => {
  const b = entry.value?.bundled;
  const items = [...(b?.datasets ?? []), ...(b?.workflows ?? []), ...(b?.tools ?? [])].map(i => i.name);
  if (!items.length) return "It has no bundled items: everything it uses is already on the platform.";
  return `${items.length} bundled ${items.length === 1 ? "item" : "items"}: ${items.join(", ")}.`;
});

function approve() {
  if (!props.projectId) return;
  started.value = true;
  void store.approve(props.projectId);
}

watch(open, isOpen => { if (isOpen) started.value = false; });
</script>

<style scoped>
/* The same look as ApproveDialog.vue. */
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
.approve__stage { margin: 0; font-size: 1rem; font-weight: 600; color: var(--text); }
.approve__result { margin: 0; font-size: 1.2rem; font-weight: 600; color: var(--text); }
.approve__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }
</style>
