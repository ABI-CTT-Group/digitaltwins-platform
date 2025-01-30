<template>
    <v-card
        class="ma-4"
        color="transparent"
        min-width="344"
        v-for="item in data"
        :key="item.name"
    >
        <v-card-text>
        <div class="text-h6 font-weight-black text-grey-lighten-2">{{ item.name }}</div>

        <div class="text-medium-emphasis text-grey-darken-2">
            {{ item.description }}
        </div>
        </v-card-text>

        <v-card-actions>
        <v-btn
            color="grey-darken-3"
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

</style>