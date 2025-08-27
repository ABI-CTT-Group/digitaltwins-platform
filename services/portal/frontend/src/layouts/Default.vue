<template>
  <v-app class="container">
    <NavHome></NavHome>

    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultView from "./View.vue";
import NavHome from "@/components/dt-components/NavHome.vue";
</script>

<style scoped>
.container {
    font-family: "Nunito", sans-serif;
    font-optical-sizing: auto;
    font-weight: 400;
    font-style: normal;
    position: relative;
    background-image: url("@/assets/login_bg.jpg"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px); 
    overflow: hidden;
}
</style>
