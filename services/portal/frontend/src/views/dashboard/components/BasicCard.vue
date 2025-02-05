<template>
    <v-card
        class="ma-4 card-color"
        color="transparent"
        min-width="344"
        max-width="444"
    >
        <v-card-text>
        <div class="text-subtitle-1 font-weight-black text-grey-darken-3">{{ data.name }}</div>

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
import { ICategoryNode } from '@/models/uiTypes';

const props = defineProps<{
    data?: ICategoryNode
}>();

</script>

<style scoped>
.card-color {
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(0,0,0,0.15) 100%), radial-gradient(at top center, rgba(255,255,255,0.40) 0%, rgba(0,0,0,0.40) 120%) #989898; background-blend-mode: multiply,multiply;
}
</style>