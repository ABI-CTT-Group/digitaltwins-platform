<template>
    <v-card
        class="ma-4 card-color"
        color="transparent"
        min-width="344"
        v-for="item in data"
        :key="item.name"
    >
        <v-card-text>
        <div class="text-h6 font-weight-black text-grey-lighten-1">{{ item.name }}</div>

        <div class="text-medium-emphasis text-grey-darken-3">
            {{ item.description }}
        </div>
        </v-card-text>

        <v-card-actions>
            <v-btn
                color="pink-darken-2"
                text="Explore"
                variant="text"
                @click = "handleExploreClicked(item.name, item.category)"
            ></v-btn>
        </v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { ICategoryNode } from '@/models/uiTypes';

const props = defineProps<{
    data?: ICategoryNode[]
}>();

const emit = defineEmits(["update:explore"])

const handleExploreClicked = (name:string, category:string) => {
    emit("update:explore", {name, category})
}
</script>

<style scoped>
.card-color {
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(0,0,0,0.15) 100%), radial-gradient(at top center, rgba(255,255,255,0.40) 0%, rgba(0,0,0,0.40) 120%) #989898; background-blend-mode: multiply,multiply;
}
</style>