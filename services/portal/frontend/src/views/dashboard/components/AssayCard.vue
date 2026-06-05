<template>
  <div class="assay-card">
    <span class="assay-card__rail" aria-hidden="true"></span>

    <div class="assay-card__head">
      <div class="assay-card__heading">
        <span class="assay-card__kind">Assay</span>
        <v-tooltip :text="capitalize(data.name)" location="top" open-delay="250">
          <template #activator="{ props: tip }">
            <span class="assay-card__name" v-bind="tip">{{ capitalize(data.name) }}</span>
          </template>
        </v-tooltip>
      </div>

      <div class="assay-card__icons">
        <v-tooltip text="Open report" location="top" open-delay="250">
          <template #activator="{ props: tip }">
            <button type="button" class="icon-btn" v-bind="tip" @click="actions.expand(data.seekId)">
              <v-icon icon="mdi-arrow-expand" size="18" />
            </button>
          </template>
        </v-tooltip>
        <v-tooltip v-if="!isClinicianView" text="Configure assay" location="top" open-delay="250">
          <template #activator="{ props: tip }">
            <button
              type="button"
              class="icon-btn icon-btn--edit"
              :disabled="configLoading"
              v-bind="tip"
              @click="openConfig"
            >
              <v-progress-circular v-if="configLoading" indeterminate size="16" width="2" />
              <v-icon v-else icon="mdi-pencil-outline" size="18" />
            </button>
          </template>
        </v-tooltip>
      </div>
    </div>

    <span v-if="data.tag" class="assay-card__tag" :style="{ '--tag': tagAccent }">{{ data.tag }}</span>
    <p v-if="data.description" class="assay-card__desc">{{ data.description }}</p>

    <div class="assay-card__actions">
      <AssayActionBar
        :is-clinician-view="isClinicianView"
        :ready="ready"
        :launching="launching"
        :can-monitor="canMonitor"
        @launch="actions.launch(data.seekId)"
        @monitor="actions.monitor(data.seekId)"
        @verify="actions.verify(data.seekId)"
        @download="actions.download(data.seekId)"
        @submit="actions.submit(data.seekId)"
      />
    </div>

    <AssayConfigDialog
      v-if="!isClinicianView"
      v-model="configOpen"
      :assay-name="data.name"
      @save="actions.save()"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { DashboardCategory } from "@/models/types";
import { capitalize } from "@/utils/common";
import { useAssayActions } from "@/composables/useAssayActions";
import AssayActionBar from "./AssayActionBar.vue";
import AssayConfigDialog from "./AssayConfigDialog.vue";

const props = defineProps<{
  data: DashboardCategory;
  isClinicianView?: boolean;
}>();

const actions = useAssayActions();
const configOpen = ref(false);

const detail = computed(() => actions.assayDetails.value[props.data.seekId]);
const exec = computed(() => actions.assayExecute.value[props.data.seekId]);

// Colour the type chip by workflow kind so GUI / Notebook / Script assays are
// distinguishable at a glance. Substring match so values like "EP3 GUI" still hit.
const tagAccent = computed(() => {
  const t = (props.data.tag ?? "").toLowerCase();
  if (t.includes("gui")) return "#5fd6e8"; // aqua
  if (t.includes("notebook")) return "#ffb74d"; // amber
  if (t.includes("script")) return "#c792ea"; // violet
  return "#9fb4bf"; // neutral fallback
});

const configLoading = computed(() => !detail.value);
const ready = computed(() => detail.value?.isAssayReadyToLaunch ?? false);
const launching = computed(() => exec.value?.isLaunching ?? false);
const canMonitor = computed(() => exec.value?.text === "Monitor");

const openConfig = () => {
  actions.openEdit(props.data.seekId);
  configOpen.value = true;
};
</script>

<style scoped>
.assay-card {
  --accent: #5fd6e8;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-height: 204px;
  padding: 22px 22px 20px;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: rgba(255, 255, 255, 0.028);
  font-family: "Nunito", sans-serif;
  overflow: hidden;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s ease, background 0.4s ease;
}
.assay-card__rail {
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.assay-card:hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  background: rgba(255, 255, 255, 0.045);
}
.assay-card:hover .assay-card__rail { transform: scaleX(1); }

.assay-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.assay-card__heading { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.assay-card__kind {
  font-size: 0.66rem;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--accent);
  opacity: 0.85;
}
.assay-card__name {
  font-size: 1.2rem;
  font-weight: 800;
  line-height: 1.2;
  color: #fff;
  /* Guard against unbounded titles: clamp to 2 lines + ellipsis, break long
     unbroken tokens, full text available via the native title tooltip. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.assay-card__icons { display: flex; gap: 6px; flex-shrink: 0; }
.icon-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  border: 1px solid rgba(120, 200, 220, 0.18);
  background: rgba(255, 255, 255, 0.03);
  color: #a4bac4;
  cursor: pointer;
  transition: border-color 0.25s ease, color 0.25s ease, background 0.25s ease;
}
.icon-btn:hover:not(:disabled) {
  border-color: rgba(95, 214, 232, 0.5);
  color: var(--accent);
  background: rgba(95, 214, 232, 0.08);
}
.icon-btn:disabled { opacity: 0.5; cursor: progress; }

/* Edit stands out in a warm orange that contrasts the cool aurora palette,
   and fills solid on hover. */
.icon-btn--edit {
  color: #ff8a5c;
  background: rgba(255, 112, 67, 0.16);
  border-color: rgba(255, 112, 67, 0.45);
  box-shadow: 0 0 0 0 rgba(255, 112, 67, 0.5);
}
.icon-btn--edit:hover:not(:disabled) {
  color: #1a0e08;
  background: #ff7043;
  border-color: #ff7043;
  box-shadow: 0 6px 16px -6px rgba(255, 112, 67, 0.8);
}

.assay-card__tag {
  --tag: #9fb4bf;
  align-self: flex-start;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--tag);
  background: color-mix(in srgb, var(--tag) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--tag) 38%, transparent);
}
.assay-card__desc {
  flex: 1;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #a4bac4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.assay-card__actions { margin-top: auto; }
</style>
