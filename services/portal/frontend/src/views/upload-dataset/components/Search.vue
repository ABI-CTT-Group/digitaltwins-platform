<template>
    <div class="d-flex justify-space-between w-100 header px-2 py-5">
        <v-text-field
            v-model="search"
            :label="label"
            variant="outlined"
            :base-color="accent"
            :color="accent"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
        />
        <v-btn
            text="search"
            :color="accent"
            variant="tonal"
            :width="150"
            rounded="lg"
            class="text-none ma-2"
            @click="handleSearch"
        ></v-btn>
    </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    label: string
    accent?: string
}>(), { accent: '#5fd6e8' })

const search = defineModel('search', {
    type: String,
    required: true
})
const emit = defineEmits(["search"])

function handleSearch() {
    emit('search')
}

</script>

<style scoped>

</style>