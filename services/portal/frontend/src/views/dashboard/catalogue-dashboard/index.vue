<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <BackIcon/>
        <div class="main-container overflow-y-auto d-flex align-center">
            <router-view/>
        </div>
    </div>
</template>

<script setup lang="ts">
import BackIcon from '@/components/commonBar/BackIcon.vue';
</script>

<style scoped>
.main-container{
    height: 95%;
    width: 100%;
}
</style>