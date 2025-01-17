<template>
  <LayoutTwoPanels ref="layoutTwoPanelsRef">
    <template #left>
      <LeftPanel :panel-width="layoutTwoPanelsRef?.leftPanelWidth"/>
    </template>
    <template #right>
      <RightPanel :panel-width="layoutTwoPanelsRef?.rightPanelWidth"/>
    </template>
  </LayoutTwoPanels>
</template>

<script setup lang="ts">
import { ref} from "vue";
import LayoutTwoPanels from "@/components/view-components/LayoutTwoPanels.vue";
import LeftPanel from "./components/left-panel-core/left.vue";
import RightPanel from "./components/right-panel-core/right.vue";

const layoutTwoPanelsRef = ref<InstanceType<typeof LayoutTwoPanels>>();

</script>

<style scoped>

</style>