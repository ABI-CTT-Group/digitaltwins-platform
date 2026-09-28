<template>
    <div class="d-flex justify-end">
        <v-btn
            color="#9fb4bf"
            text="refresh"
            variant="text"
            prepend-icon="mdi-refresh"
            rounded="lg"
            class="text-none ma-2"
            @click="handleRefresh"
        ></v-btn>
    </div>
</template>

<script setup lang="ts">
const emit = defineEmits(["refresh"])
function handleRefresh() {
    emit('refresh')
}
</script>

<style scoped>

</style>