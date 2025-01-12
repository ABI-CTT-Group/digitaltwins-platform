<template>
  <v-app>
    <default-bar title="Tumour Position Study" version="v3.0.0">
      <NavPanel />
    </default-bar>

    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultBar from "../components/AppBar.vue";
import DefaultView from "./View.vue";
import NavPanel from "@/components/nav-calculation/NavPanel.vue";
</script>

<style></style>
