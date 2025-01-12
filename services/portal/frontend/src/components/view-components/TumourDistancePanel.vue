<template>
    <v-card >
      <div class="dts"><span>DTS:</span> <span>{{ dts }} mm</span></div>
      <div class="dtn"><span>DTN:</span> <span>{{ dtn }} mm</span></div>
      <div class="dtr"><span>DTR:</span> <span>{{ dtr }} mm</span></div>
    </v-card>
</template>

<script setup lang="ts">
defineProps({
  dts: Number,
  dtn: Number,
  dtr: Number
})
</script>

<style scoped>

</style>