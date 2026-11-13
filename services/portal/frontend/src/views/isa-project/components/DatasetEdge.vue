<template>
  <BaseEdge :id="id" :path="path[0]" :marker-end="markerEnd" />
  <EdgeLabelRenderer v-if="data.labels.length">
    <div
      class="edge-label nodrag nopan"
      :class="{ 'is-planned': data.planned }"
      :style="{ transform: `translate(-50%, -50%) translate(${path[1]}px, ${path[2]}px)` }"
    >
      <span v-for="l in data.labels" :key="l" class="edge-label__item">
        <span class="edge-label__dataset">{{ split(l)[0] }}</span>
        <span v-if="split(l)[1]" class="edge-label__port">{{ split(l)[1] }}</span>
      </span>
    </div>
  </EdgeLabelRenderer>
</template>

<script setup lang="ts">
// A study graph edge whose label stacks each planned dataset's name over the port that fills it,
// so a long "dataset / port" fits the gap between two columns.
import { computed } from "vue";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type Position } from "@vue-flow/core";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition: Position;
  targetPosition: Position;
  markerEnd?: string;
  data: { labels: string[]; planned: boolean };
}>();

const path = computed(() => getSmoothStepPath(props));

/** "dataset / port" as [dataset, port]; any other label is one line. */
const split = (label: string): [string, string?] => {
  const at = label.lastIndexOf(" / ");
  return at < 0 ? [label] : [label.slice(0, at), label.slice(at + 3)];
};
</script>

<style scoped>
.edge-label {
  position: absolute;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 150px;
  padding: 3px 7px;
  border-radius: 6px;
  background: #0a1a24;
  font-family: var(--font-ui);
  font-size: 11px;
  line-height: 1.25;
  pointer-events: none;
}
.edge-label__item { display: flex; flex-direction: column; min-width: 0; }
.edge-label__dataset { color: var(--text-dim); overflow-wrap: anywhere; }
.edge-label__port { color: var(--text-faint); overflow-wrap: anywhere; }
.edge-label.is-planned { font-style: italic; }
</style>
