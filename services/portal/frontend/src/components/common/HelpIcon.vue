<template>
   <div>
        <v-btn 
            variant="tonal"
            class="hover-animate heartbeat btn"
            :size="size || 60"
            >
            <v-icon 
                class="icon"
                icon="mdi-help-network-outline" 
                size="25"
                color="deep-orange"
            >
            </v-icon>
        </v-btn>
    </div>
</template>

<script setup lang="ts">

defineProps<{
  size?: number;
}>()
</script>

<style scoped>

</style>