<template>
    <div class="d-flex justify-space-between align-center h-screen">
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

</style>