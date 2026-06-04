<template>
  <v-main>
    <router-view />
  </v-main>
</template>

<script lang="ts" setup>
//
</script>
<style scoped>
/* Fill the v-app shell (already 100vh) WITHOUT adding the app-bar's
   injected padding-top on top of 100vh — using 100% avoids clipping
   the bottom of the page by the navbar height. */
.v-main {
  height: 100%;
  overflow-y: auto;
}
</style>