<template>
    <div class="d-flex justify-end">
        <v-btn
            color="blue"
            :text="'refresh'"
            variant="tonal"
            :width="150"
            rounded="md"
            class="hover-animate ma-2"
            @click="handleRefresh"
        ></v-btn>
    </div>
</template>

<script setup lang="ts">
const emit = defineEmits(["on:refresh"])
function handleRefresh() {
    emit('on:refresh')
}
</script>

<style scoped>

</style>