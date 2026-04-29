<template>
    <div class="back-arrow">
        <v-btn 
            icon="mdi-arrow-left" 
            variant="tonal"
            class="hover-animate"
            size="65"
            @click="$router.back()"
            ></v-btn>
    </div>
</template>

<script setup lang="ts">

</script>

<style scoped>
.back-arrow {
  position: fixed;
  top: 80px;
  left: 20px;
  z-index: 100;
}
</style>