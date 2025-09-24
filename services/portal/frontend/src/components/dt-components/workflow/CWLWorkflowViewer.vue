<script setup lang="ts">
import { ref, watch, h, nextTick } from "vue"
import { VueFlow, Handle, Position, MarkerType, useVueFlow } from "@vue-flow/core"
import "@vue-flow/core/dist/style.css"
import "@vue-flow/core/dist/theme-default.css"

const props = defineProps<{ workflow: any }>()

const nodes = ref<any>([])
const edges = ref<any>([])
const { fitView } = useVueFlow()

const StepNode = (props: any) => {
  const stepId = props.id
  const step = props.data.step

  return h(
    "div",
    { class: "step-node" },
    [
      h("div", { class: "port-container" },
        Object.keys(step?.in || {}).map(inputKey =>
          h(Handle, {
            type: "target",
            position: Position.Left,
            id: `${stepId}-in-${inputKey}`,
            class: "input-port"
          })
        )
      ),
      h("div", { class: "step-label" }, `⚙️ ${stepId}`),
      h("div", { class: "port-container" },
        (step?.out || []).map((outputKey: any) =>
          h(Handle, {
            type: "source",
            position: Position.Right,
            id: `${stepId}-out-${outputKey}`,
            class: "output-port"
          })
        )
      )
    ]
  )
}

const nodeTypes = { stepNode: StepNode }

function parseWorkflow(cwl: any) {
  const parsedNodes: any[] = []
  const parsedEdges: any[] = []

  Object.entries(cwl.inputs || {}).forEach(([key, val]: any, idx) => {
    parsedNodes.push({
      id: key,
      type: "input",
      position: { x: 0, y: idx * 120 },
      data: { label: key },
      class: "input-node"
    })
  })

  Object.entries(cwl.steps || {}).forEach(([stepId, step]: any, idx) => {
    parsedNodes.push({
      id: stepId,
      type: "stepNode",
      position: { x: 350, y: idx * 200 },
      data: { step },
    })

    Object.entries(step.in || {}).forEach(([inKey, source]: any) => {
      const sourceId = source.includes("/") ? source.split("/")[0] : source
      parsedEdges.push({
        id: `${sourceId}-${stepId}-${inKey}`,
        source: sourceId,
        target: stepId,
        targetHandle: `${stepId}-in-${inKey}`,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: true,
      })
    })
  })

  Object.entries(cwl.outputs || {}).forEach(([outId, out]: any, idx) => {
    parsedNodes.push({
      id: outId,
      type: "output",
      position: { x: 900, y: idx * 120 },
      data: { label: outId },
      class: "output-node"
    })

    const [sourceStep, outputKey] = out.outputSource.split("/")
    parsedEdges.push({
      id: `${sourceStep}-${outId}`,
      source: sourceStep,
      sourceHandle: `${sourceStep}-out-${outputKey}`,
      target: outId,
      type: "smoothstep",
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: true,
    })
  })

  nodes.value = parsedNodes
  edges.value = parsedEdges
}

watch(
  () => props.workflow,
  async (newVal) => {
    if (newVal) {
      parseWorkflow(newVal)
      await nextTick()
    //   fitView({ padding: 0.2, duration: 800 })
    setTimeout(() => {
        fitView({ padding: 0.2, duration: 800 })
      }, 50)

    }
  },
  { immediate: true, deep: true }
)
</script>

<template>
  <div class="workflow-container">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :node-types="nodeTypes"
      fit-view
      :nodes-draggable="true"
      :nodes-connectable="true"
      :edges-updatable="true"
      :zoom-on-scroll="true"
      :pan-on-drag="true"
      @pane-ready="fitView({ padding: 0.2, duration: 800 })"
    />
  </div>
</template>

<style scoped>
.workflow-container {
  width: 100%;
  height: 600px;
  border: 1px solid #ccc;
  border-radius: 8px;
  /* background: #f8fafc; */
}


.input-node {
  background: #1976d2;
  color: #fff;
  padding: 8px 12px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: 0 3px 6px rgba(0,0,0,0.25);
}


.output-node {
  background: #43a047;
  color: #fff;
  padding: 8px 12px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: 0 3px 6px rgba(0,0,0,0.25);
}

.step-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 180px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f5f5f5;
  border: 1px solid #ccc;
  box-shadow: 0 3px 6px rgba(0,0,0,0.15);
}

.step-label {
  flex: 1;
  text-align: center;
  font-weight: 600;
}

.port-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-port {
  background: #1976d2;
  width: 10px;
  height: 10px;
}

.output-port {
  background: #43a047;
  width: 10px;
  height: 10px;
}
</style>
