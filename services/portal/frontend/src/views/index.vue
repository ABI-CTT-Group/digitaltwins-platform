<template>
    <div class="d-flex justify-space-between align-center h-screen gradinates">
        <div class="fill-height w-50">
            <v-img
                :aspect-ratio="1"
                class="fill-height"
                :src="logoImg"
                cover
            ></v-img>
        </div>
        <div class="w-50 fill-height">
            <LoginPage />
        </div>
    </div>
</template>

<script setup lang="ts">
import LoginPage from './login/index.vue'
import logoImg from '@/assets/logo.jpg'
</script>

<style scoped>
.gradinates {
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(0,0,0,0.15) 100%), radial-gradient(at top center, rgba(255,255,255,0.40) 0%, rgba(0,0,0,0.40) 120%) #989898; background-blend-mode: multiply,multiply;
}
</style>