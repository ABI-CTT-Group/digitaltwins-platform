<template>
    <div class="d-flex justify-space-between w-100 header px-2 py-5">
        <v-text-field
            v-model="search"
            :label="label"
            variant="outlined"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
        />
        <v-btn
            :text="'search'"
            variant="tonal"
            :width="150"
            rounded="md"
            class="hover-animate ma-2"
            @click="handleSearch"
        ></v-btn>
    </div>
</template>

<script setup lang="ts">
defineProps<{
    label: string
}>()

const search = defineModel('search', {
    type: String,
    required: true
})
const emit = defineEmits(["on:search"])

function handleSearch() {
    emit('on:search')
}

</script>

<style scoped>

</style>