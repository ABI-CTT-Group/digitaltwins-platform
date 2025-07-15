<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <NavHome>
            <h1 class="mx-auto">Catalogue Dashboard</h1>
        </NavHome>
        <div class="main-container overflow-y-auto d-flex align-center">
            <router-view/>
        </div>
    </div>
</template>

<script setup lang="ts">
import NavHome from '@/views/dashboard/components/NavHome.vue';

</script>

<style scoped>
.container {
    height: 100vh;
    position: relative;
    background-image: url("@/assets/login_bg.jpg"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px); 
}
.container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: inherit; 
  filter: blur(10px); 
  -webkit-filter: blur(10px); 
  z-index: -1; 
}
.main-container{
    width: 80%;
    padding-top: 100px;
    height: 95%;
}
</style>