<template>
    <v-card
        class="w-75 ma-4 card-color"
        color="grey-darken-1"
    >
        <v-card-text>
        <div class="text-subtitle-1 font-weight-black text-grey-lighten-3">{{ data.name }}</div>

        <div class="text-medium-emphasis text-grey-darken-3">
            {{ data.description }}
        </div>
        </v-card-text>

        <v-card-actions class="d-flex justify-space-between px-10">
            <slot name="action"></slot>
        </v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { IDashboardCategory } from '@/models/apiTypes';

const props = defineProps<{
    data: IDashboardCategory
}>();

</script>

<style scoped>
.card-color {
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(0,0,0,0.45) 100%), radial-gradient(at top center, rgba(255,255,255,0.30) 0%, rgba(0,0,0,0.60) 120%) #000; background-blend-mode: multiply,multiply;
    background-color: transparent !important;
}
</style>