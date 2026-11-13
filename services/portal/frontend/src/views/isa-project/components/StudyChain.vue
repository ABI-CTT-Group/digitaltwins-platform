<template>
  <div class="chain">
    <span class="chain__study">{{ study.title }}</span>
    <p v-if="!columns.length" class="chain__empty">No assays yet</p>
    <div v-else class="chain__line" data-test="chain" role="img" :aria-label="readout">
      <div v-for="(col, n) in columns" :key="n" class="chain__col" :class="{ 'chain__col--fork': col.length > 1 }" data-test="chain-column">
        <span
          v-for="a in col"
          :key="a.id"
          class="chip"
          :style="{ '--tag': ASSAY_TYPE_ACCENT[a.type] ?? '#9fb4bf' }"
          :data-type="a.type"
          :title="a.title"
          data-test="chain-chip"
        ><span class="chip__text">{{ a.title }}</span></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// A study's assays as a short line on the ISA project hub (prototype). It uses the Flow view's
// columns and its line language: dashed, because nothing on the hub has run yet, and a fork drawn
// as a branch.
import { computed } from "vue";
import type { Assay, Catalogue, Study } from "../model/types";
import { ASSAY_TYPE_ACCENT, emptySim, studyGraph } from "../model/isaProject";

const props = defineProps<{ study: Study }>();

// Only the assays are drawn, so the graph needs no catalogue.
const NO_CATALOGUE: Catalogue = { workflows: [], tools: [], datasets: [] };

const columns = computed(() => {
  const byColumn = new Map<number, { row: number; assay: Assay }[]>();
  for (const n of studyGraph(props.study, NO_CATALOGUE, emptySim()).nodes) {
    const assay = props.study.assays.find(a => a.id === n.assayId);
    if (n.kind !== "assay" || !assay) continue;
    byColumn.set(n.column, [...(byColumn.get(n.column) ?? []), { row: n.row, assay }]);
  }
  return [...byColumn].sort(([a], [b]) => a - b)
    .map(([, col]) => col.sort((a, b) => a.row - b.row).map(x => x.assay));
});

const readout = computed(() =>
  `${props.study.title} runs ${columns.value.map(col => col.map(a => a.title).join(" and ")).join(", then ")}.`);
</script>

<style scoped>
.chain { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; min-width: 0; }
.chain__study { font-size: 0.8rem; color: var(--text-faint); }
.chain__empty { margin: 0; font-size: 0.8rem; color: var(--text-faint); }

/* Columns left to right; the connectors are drawn in the gap before each column after the first. */
.chain__line { --gap: 30px; --chip-h: 28px; display: flex; align-items: center; max-width: 100%; overflow-x: auto; padding: 2px 0; }
.chain__col { position: relative; display: flex; flex-direction: column; gap: 8px; }
.chain__col + .chain__col { margin-left: var(--gap); }
/* The line in from the previous column, to the middle of the gap. */
.chain__col + .chain__col::before {
  content: "";
  position: absolute;
  top: 50%;
  left: calc(-1 * var(--gap));
  width: calc(var(--gap) / 2);
  border-top: 1.5px dashed var(--text-faint);
}
/* A fork: one upright joining the branches. */
.chain__col + .chain__col--fork::after {
  content: "";
  position: absolute;
  top: calc(var(--chip-h) / 2);
  bottom: calc(var(--chip-h) / 2);
  left: calc(-1 * var(--gap) / 2);
  border-left: 1.5px dashed var(--text-faint);
}

.chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: var(--chip-h);
  max-width: 240px;
  padding: 0 11px;
  border: 1px solid color-mix(in srgb, var(--tag) 40%, transparent);
  border-left: 3px solid var(--tag);
  border-radius: 8px;
  background: color-mix(in srgb, var(--tag) 9%, transparent);
  color: var(--text);
  font-size: 0.8rem;
}
.chip__text { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
/* Each branch's own line, from the middle of the gap. */
.chain__col + .chain__col .chip::before {
  content: "";
  position: absolute;
  top: 50%;
  left: calc(-1 * var(--gap) / 2 - 3px);
  width: calc(var(--gap) / 2);
  border-top: 1.5px dashed var(--text-faint);
}
</style>
