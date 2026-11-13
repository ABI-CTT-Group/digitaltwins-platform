<template>
  <div class="card" :class="[`status--${status}`, { 'is-selected': selected }]">
    <span class="card__rail" aria-hidden="true"></span>

    <div class="card__head">
      <div class="card__heading">
        <span class="card__kind">Assay</span>
        <span class="card__name" :title="assay.title">{{ assay.title }}</span>
      </div>
      <div class="card__icons nodrag nopan">
        <v-tooltip text="Open assay" location="top" open-delay="250">
          <template #activator="{ props: tip }">
            <button type="button" class="icon-btn" data-test="expand" v-bind="tip" @click.stop="emit('configure')">
              <v-icon icon="mdi-arrow-expand" size="18" />
            </button>
          </template>
        </v-tooltip>
        <v-tooltip text="Configure assay" location="top" open-delay="250">
          <template #activator="{ props: tip }">
            <button type="button" class="icon-btn icon-btn--edit" data-test="configure" v-bind="tip" @click.stop="emit('configure')">
              <v-icon icon="mdi-pencil-outline" size="18" />
            </button>
          </template>
        </v-tooltip>
      </div>
    </div>

    <div class="card__meta">
      <span class="card__tag" :style="{ '--tag': tagAccent }">{{ assay.type }}</span>
      <span class="card__status" data-test="status">{{ STATUS_TEXT[status] }}</span>
      <v-tooltip v-if="warnings?.length" :text="warnings.join(' ')" location="top" open-delay="150">
        <template #activator="{ props: tip }">
          <span class="card__warn" role="img" data-test="cohort-warning" :aria-label="warnings.join(' ')" v-bind="tip">
            <v-icon icon="mdi-alert-outline" size="16" /> Cohort
          </span>
        </template>
      </v-tooltip>
    </div>

    <div class="card__actions nodrag nopan">
      <AssayActionBar
        :ready="status === 'ready' || status === 'ran' || status === 'submitted'"
        :can-monitor="false"
        :is-script="assay.type === 'script'"
        :is-notebook="assay.type === 'notebook'"
        @launch="emit('launch')"
        @monitor="emit('unavailable', 'Monitor')"
        @verify="emit('unavailable', 'Verify')"
        @download="emit('unavailable', 'Download')"
        @submit="emit('submit')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
// One assay of a sandbox study (prototype), shown in both the List and the Flow view. It looks
// like the dashboard's real assay card; Launch and Submit are simulated, the other actions aren't.
import { computed } from "vue";
import AssayActionBar from "@/views/dashboard/components/AssayActionBar.vue";
import type { Assay } from "../model/types";
import { ASSAY_TYPE_ACCENT, type AssayStatus } from "../model/isaProject";

const props = defineProps<{ assay: Assay; status: AssayStatus; selected?: boolean; warnings?: string[] }>();
const emit = defineEmits<{
  (e: "configure"): void;
  (e: "launch"): void;
  (e: "submit"): void;
  (e: "unavailable", action: string): void;
}>();

const STATUS_TEXT: Record<AssayStatus, string> = {
  unconfigured: "Needs configuring",
  blocked: "Waiting on earlier assays",
  ready: "Ready to run",
  ran: "Run, not submitted",
  submitted: "Submitted (simulated)",
};

// The same type colours as the real assay cards.
const tagAccent = computed(() => ASSAY_TYPE_ACCENT[props.assay.type] ?? "#9fb4bf");
</script>

<style scoped>
.card {
  --accent: #5fd6e8;
  --state: var(--text-faint);
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  padding: 20px 20px 18px;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: #0d2230;
  font-family: "Nunito", sans-serif;
  text-align: left;
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.card.status--ready { --state: var(--accent-tools); }
.card.status--blocked { --state: var(--tone-needs); }
.card.status--unconfigured { --state: var(--tone-needs); }
.card.status--ran { --state: #9fb4bf; }
.card.status--submitted { --state: var(--accent-measurements); }
.card:hover { border-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.card.is-selected { border-color: var(--accent-tools); box-shadow: 0 0 0 1px var(--accent-tools); }

/* The rail shows the run status, so it is always visible here. */
.card__rail {
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 3px;
  border-radius: 0 0 3px 3px;
  background: var(--state);
}

.card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.card__heading { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.card__kind { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent); opacity: 0.85; }
.card__name {
  font-size: 1.08rem;
  font-weight: 800;
  line-height: 1.25;
  color: #fff;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.card__icons { display: flex; gap: 6px; flex-shrink: 0; }
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
}
.icon-btn:hover { border-color: rgba(95, 214, 232, 0.5); color: var(--accent); }
.icon-btn--edit { color: #ff8a5c; background: rgba(255, 112, 67, 0.16); border-color: rgba(255, 112, 67, 0.45); }
.icon-btn--edit:hover { color: #1a0e08; background: #ff7043; border-color: #ff7043; }

.card__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.card__tag {
  --tag: #9fb4bf;
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
.card__status { display: inline-flex; align-items: center; gap: 6px; font-size: 0.8rem; color: var(--text-dim); }
.card__status::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--state); }
.card__warn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--tone-needs);
  background: color-mix(in srgb, var(--tone-needs) 14%, transparent);
}
.card__actions { margin-top: auto; cursor: default; }
</style>
