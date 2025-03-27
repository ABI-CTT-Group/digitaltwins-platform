<template>
    <v-card
        :disabled="loading"
        :loading="loading"
        class="mx-auto my-12"
        max-width="450"
        :color="'grey-lighten-2'"
        :variant="'flat'"
    >
        <template v-slot:loader="{ isActive }">
        <v-progress-linear
            :active="isActive"
            color="deep-purple"
            height="4"
            indeterminate
        ></v-progress-linear>
        </template>

        <v-img
            height="250"
            :src="src"
            aspect-ratio="16/9"
            cover
        ></v-img>

        <v-card-item>
        <v-card-title>{{ title }}</v-card-title>

        <v-card-subtitle>
            <span class="me-1">{{ location }}</span>

            <v-icon
            color="error"
            icon="mdi-fire-circle"
            size="small"
            ></v-icon>
        </v-card-subtitle>
        </v-card-item>

        <v-card-text>
            <div>{{ description }}</div>
        </v-card-text>

        <v-divider class="mx-4 mb-1"></v-divider>

        <!-- <v-card-title>Tonight's availability</v-card-title> -->

        <!-- <div class="px-4 mb-2">
            <v-chip-group v-model="selection" selected-class="bg-deep-purple-lighten-2">
                <v-chip>5:30PM</v-chip>

                <v-chip>7:30PM</v-chip>

                <v-chip>8:00PM</v-chip>

                <v-chip>9:00PM</v-chip>
            </v-chip-group>
        </div> -->

        <v-card-actions>
        <v-btn
            color="deep-purple-lighten-2"
            text="Explore"
            block
            border
            @click="explore"
        ></v-btn>
        </v-card-actions>
    </v-card>
</template>

<script lang="ts" setup>
import { ref } from 'vue'

const props = defineProps({
  src: String,
  title: String,
  location: String,
  description: String
})

const emit = defineEmits(['on-explore'])

const loading = ref(false)
function explore () {
  loading.value = true
  setTimeout(() => {
    emit('on-explore', props.title)
    loading.value = false
}, 1000)
}
</script>

<style scoped>
</style>