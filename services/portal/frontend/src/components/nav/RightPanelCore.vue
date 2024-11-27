<template>
    <v-list-group value="RightPanelCtl">
      <template v-slot:activator="{ props }">
        <v-list-item
          v-bind="props"
          color="primary"
          prepend-icon="mdi-video-3d"
          title="RightPanelCtl"
        ></v-list-item>
      </template>
  
      <RightPanelCtl />
    </v-list-group>
  </template>
  
  <script setup lang="ts">
  import RightPanelCtl from "@/components/nav/tools/RightPanelCtl.vue";

  </script>
  
  <style scoped></style>
  