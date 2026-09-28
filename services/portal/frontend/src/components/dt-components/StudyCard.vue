<template>
    <v-card
        class="mx-auto"
        max-width="350"
        min-width="350"
    >
        <v-img
            class="align-end text-white"
            height="200"
            :src="study.src"
            cover
        >
            <v-card-title>{{ study.name }}</v-card-title>
        </v-img>
        <v-card-subtitle class="pt-4">
            {{ study.subTitle }}
        </v-card-subtitle>

        <v-card-text>
            <div>{{ study.description }}</div>
        </v-card-text>

        <v-card-actions>
            <v-btn v-if="!study.isEnter" color="green" text="Enter" @click="handleEnter(study)"></v-btn>
            <v-btn v-if="study.isEnter" color="orange" text="Begin session" @click="handleStartSession(study.session)"></v-btn>
            <v-btn v-if="study.isEnter" color="orange" text="Tutorial"></v-btn>
        </v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { IStudy } from "@/models/uiTypes";
import { useRouter } from "vue-router";

const props = defineProps<{
    study: IStudy
}>();
const emit = defineEmits(["update:enter-clicked"]);
const router = useRouter();

const handleEnter = (study: IStudy) => {
    study.isEnter=!study.isEnter
    emit("update:enter-clicked", study)   
}
const handleStartSession = (session: string) => {
    if (session === "") return;
    router.push({name: session})
}
</script>

<style scoped>

</style>