<template>
  <router-view />
  <!-- Outside the router-view so it survives navigation and covers every route,
       including /tool-view which renders outside the default layout. -->
  <SessionGuard />
</template>

<script lang="ts" setup>
import SessionGuard from "@/components/SessionGuard.vue";
</script>

<style>

</style>
