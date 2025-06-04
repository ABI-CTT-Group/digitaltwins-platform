<template>
    <div class="logo">
        <v-icon
            class="cursor-pointer"
            color="green-darken-2"
            icon="mdi-domain"
            size="large"
        ></v-icon>
    </div>
</template>

<script setup lang="ts">

</script>

<style scoped>
.logo{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 60px;
    border-bottom-left-radius: 3px;
    border-bottom-right-radius: 3px;
    padding: 0 20px;
    background: rgba(255, 255, 255, 0.2); 
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); 
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px);
    z-index: 1000;
}
</style>