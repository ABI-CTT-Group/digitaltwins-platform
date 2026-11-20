<template>
  <div class="graph" :class="{ 'graph--tb': direction === 'TB' }">
    <VueFlow
      id="isa-study-graph"
      :nodes="nodes"
      :edges="edges"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :elements-selectable="false"
      :min-zoom="0.25"
      :max-zoom="1.5"
      @node-click="onNodeClick"
    >
      <template #node-assay="{ data }">
        <Handle type="target" :position="inSide" />
        <SandboxAssayCard
          :assay="data.assay"
          :status="data.status"
          :selected="data.assay.id === selectedAssayId"
          @configure="emit('configure', data.assay.id)"
          :warnings="data.warnings"
          :platform="platform?.[data.assay.id]"
          @launch="emit('launch', data.assay.id)"
          @submit="emit('submit', data.assay.id)"
          @monitor="emit('monitor', data.assay.id)"
          @verify="emit('verify', data.assay.id)"
          @download="emit('download', data.assay.id)"
        />
        <Handle type="source" :position="outSide" />
      </template>
      <template #edge-dataset="edgeProps">
        <DatasetEdge v-bind="edgeProps" />
      </template>
      <template #node-source="{ data }">
        <v-icon icon="mdi-database-outline" size="16" />
        <span class="node-source__label">{{ data.label }}</span>
        <span v-if="data.bundled" class="node-source__bundled" title="Bundled with this project, not on the platform yet">Bundled</span>
        <Handle type="source" :position="outSide" />
      </template>
    </VueFlow>

    <div class="zoom">
      <button type="button" aria-label="Zoom in" @click="zoomIn()"><v-icon icon="mdi-plus" size="18" /></button>
      <button type="button" aria-label="Zoom out" @click="zoomOut()"><v-icon icon="mdi-minus" size="18" /></button>
      <button type="button" aria-label="Fit to view" @click="refit()"><v-icon icon="mdi-fit-to-screen-outline" size="18" /></button>
    </div>
  </div>
</template>

<script setup lang="ts">
// The selected study as a flow of assays, top to bottom or left to right. Each edge carries the
// datasets one assay hands the next; it is dashed while they are still planned. Datasets already on
// the platform are small pills before the assay that reads them.
import { computed, watch } from "vue";
import { VueFlow, Handle, Position, MarkerType, useVueFlow, type NodeMouseEvent } from "@vue-flow/core";
import "@vue-flow/core/dist/style.css";
import SandboxAssayCard from "./SandboxAssayCard.vue";
import DatasetEdge from "./DatasetEdge.vue";
import type { Catalogue, Study } from "../model/types";
import { cohortWarnings, cohortWarningText, studyGraph, type Sim } from "../model/isaProject";
import type { PlatformLink } from "../platformRun";

const props = defineProps<{
  study: Study;
  catalogue: Catalogue;
  sim: Sim;
  selectedAssayId: string | null;
  /** Sandbox assay id → the platform assay it runs, for a project linked to the platform. */
  platform?: Record<string, PlatformLink>;
  /** Top to bottom (TB) or left to right (LR). */
  direction: "TB" | "LR";
}>();
const emit = defineEmits<{
  (e: "configure" | "launch" | "submit" | "monitor" | "verify" | "download", assayId: string): void;
}>();

const CARD_WIDTH = 330;
/** studyGraph() puts each node in a column (its step in the run) and a row (its place in that
 *  step). Left to right, a column runs across and a row down; top to bottom, the other way round.
 *  `step`: between columns, with room for the edge labels; `row`: between rows; `sourceOffset`:
 *  a dataset pill against the card it feeds; `sourceGap`: between pills. */
const SPACING = {
  LR: { step: CARD_WIDTH + 130, row: 290, sourceOffset: 60, sourceGap: 44 },
  // A pill sits right of the card's centre, clear of the label (up to 150 wide) on the edge coming in.
  TB: { step: 420, row: CARD_WIDTH + 60, sourceOffset: CARD_WIDTH / 2 + 85, sourceGap: 240 },
};
const CARD_CLEARANCE = 250; // left to right: below an assay card, for a dataset pill in the same column
const SOURCE_LEAD = 110; // top to bottom: a dataset pill just above the card it feeds
/** Below this the cards can't be read, so a wide study is panned rather than squeezed. */
const MIN_READABLE_ZOOM = 0.7;

const graph = computed(() => studyGraph(props.study, props.catalogue, props.sim));
const spacing = computed(() => SPACING[props.direction]);
const inSide = computed(() => (props.direction === "TB" ? Position.Top : Position.Left));
const outSide = computed(() => (props.direction === "TB" ? Position.Bottom : Position.Right));

const columnSize = computed(() => {
  const size = new Map<number, number>();
  for (const n of graph.value.nodes) if (n.kind === "assay") size.set(n.column, (size.get(n.column) ?? 0) + 1);
  return size;
});

// Rows are centred on each other, so a lone assay sits level with the middle of its neighbours.
const rowAt = (column: number, row: number) => (row - ((columnSize.value.get(column) ?? 1) - 1) / 2) * spacing.value.row;

/** Left to right, a platform dataset sits in the column before its first reader, level with it, so
 *  its edge runs straight across instead of behind other cards; in a column that also holds assays
 *  it starts below the last card. Top to bottom, it sits just above its first reader. Either way,
 *  one that would overlap another dataset moves along the row. */
const sourcePosition = computed(() => {
  const tb = props.direction === "TB";
  const { step, sourceOffset, sourceGap } = spacing.value;
  const at = new Map<string, { x: number; y: number }>();
  const placed = new Map<number, number[]>();
  const floor = new Map<number, number>();
  for (const n of graph.value.nodes) {
    if (n.kind === "assay" && !tb) floor.set(n.column, Math.max(floor.get(n.column) ?? -Infinity, rowAt(n.column, n.row) + CARD_CLEARANCE));
  }
  for (const n of graph.value.nodes) {
    if (n.kind !== "source") continue;
    const target = graph.value.edges.find(e => e.source === n.id)?.target;
    const t = graph.value.nodes.find(m => m.id === target);
    if (!t) continue;
    const band = tb ? t.column : n.column;
    let r = Math.max(rowAt(t.column, t.row) + sourceOffset, floor.get(band) ?? -Infinity);
    const taken = placed.get(band) ?? [];
    while (taken.some(p => Math.abs(p - r) < sourceGap)) r = Math.max(...taken.filter(p => Math.abs(p - r) < sourceGap)) + sourceGap;
    placed.set(band, [...taken, r]);
    at.set(n.id, position(tb ? t.column * step - SOURCE_LEAD : n.column * step, r));
  }
  return at;
});

/** A point `along` the run and `across` it, on screen. */
const position = (along: number, across: number) => (props.direction === "TB" ? { x: across, y: along } : { x: along, y: across });

const nodes = computed(() => graph.value.nodes.map(n => ({
  id: n.id,
  type: n.kind,
  position: sourcePosition.value.get(n.id) ?? position(n.column * spacing.value.step, rowAt(n.column, n.row)),
  data: n.kind === "assay"
    ? {
        assay: props.study.assays.find(a => a.id === n.assayId),
        status: n.status,
        warnings: cohortWarnings(props.study, n.assayId!).map(cohortWarningText),
      }
    : { label: n.label, bundled: n.bundled },
  class: `node-${n.kind}`,
})));

const edges = computed(() => graph.value.edges.map(e => ({
  id: e.id,
  source: e.source,
  target: e.target,
  type: "dataset",
  data: { labels: e.labels, planned: e.planned },
  markerEnd: MarkerType.ArrowClosed,
  class: e.planned ? "edge-planned" : "",
})));

const { fitView, zoomIn, zoomOut, setViewport, dimensions, getNodes, onNodesInitialized } = useVueFlow("isa-study-graph");
const refit = () => fitView({ padding: 0.06, duration: 250 });

/** Show the whole study if it fits at a readable zoom; otherwise start at its first assays (the top
 *  or left edge, where a run begins), centred the other way, and let the user pan. */
function place() {
  const ns = getNodes.value;
  const { width, height } = dimensions.value;
  if (!ns.length || !width) return;
  const pad = 32;
  const minX = Math.min(...ns.map(n => n.position.x));
  const maxX = Math.max(...ns.map(n => n.position.x + (n.dimensions?.width ?? 0)));
  const minY = Math.min(...ns.map(n => n.position.y));
  const maxY = Math.max(...ns.map(n => n.position.y + (n.dimensions?.height ?? 0)));
  const fit = Math.min((width - 2 * pad) / (maxX - minX || 1), (height - 2 * pad) / (maxY - minY || 1));
  const zoom = Math.min(1, Math.max(MIN_READABLE_ZOOM, fit));
  const x = Math.max(pad, (width - (maxX - minX) * zoom) / 2) - minX * zoom;
  const y = Math.max(pad, (height - (maxY - minY) * zoom) / 2) - minY * zoom;
  setViewport({ x, y, zoom }, { duration: 250 });
}

// Re-place whenever the layout changes: a newly linked input can move an assay to another column.
onNodesInitialized(() => setTimeout(place, 60));
watch(() => nodes.value.map(n => `${n.id}@${n.position.x},${n.position.y}`).join("|"), () => setTimeout(place, 60));

// Clicking a card opens it; its own buttons stop the click first.
function onNodeClick({ node }: Pick<NodeMouseEvent, "node">) {
  if (node.type === "assay") emit("configure", node.data.assay.id);
}
</script>

<style scoped>
/* vue-flow fills its parent, so the parent needs a definite height. */
.graph {
  position: relative;
  width: 100%;
  height: 640px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: radial-gradient(circle, rgba(164, 186, 196, 0.16) 1px, transparent 1px) 0 0 / 22px 22px;
}

/* vue-flow renders nodes outside this component's scope, so these rules go through :deep. */
/* Top to bottom, a study runs down the page, so the canvas takes most of the window. */
.graph--tb { height: max(640px, 80vh); }

.graph :deep(.vue-flow__node) { font-family: var(--font-ui); color: var(--text); }
.graph :deep(.vue-flow__handle) { opacity: 0; pointer-events: none; }
.graph :deep(.node-assay) { width: 330px; cursor: pointer; }

.graph :deep(.node-source) {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1.5px solid var(--accent-measurements);
  background: color-mix(in srgb, var(--accent-measurements) 16%, #0a1a24);
  font-size: 0.8rem;
}
.graph :deep(.node-source__label) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.graph :deep(.node-source__bundled) {
  flex: none;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--accent-measurements);
  color: var(--ink);
  font-size: 0.7rem;
  font-weight: 600;
}

.graph :deep(.vue-flow__edge-path) { stroke: #8fa6b2; stroke-width: 1.5; }
.graph :deep(.edge-planned .vue-flow__edge-path) { stroke: var(--text-faint); stroke-dasharray: 6 5; }

.zoom {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.zoom button {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: #0d2230;
  color: var(--text-dim);
  cursor: pointer;
}
.zoom button:hover { color: var(--text); border-color: var(--accent-tools); }
.zoom button:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: 2px; }
</style>
