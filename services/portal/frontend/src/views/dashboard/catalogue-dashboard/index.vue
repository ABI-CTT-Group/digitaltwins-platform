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
.container{
  background: #556270;  
  background: -webkit-linear-gradient(to right, #FF6B6B, #556270);  
  background: linear-gradient(to right, #FF6B6B, #556270); 
}
.main-container{
    width: 80%;
    padding-top: 100px;
    height: 95%;
}
</style>