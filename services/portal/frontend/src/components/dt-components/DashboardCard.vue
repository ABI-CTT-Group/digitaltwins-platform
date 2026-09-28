<template>
    <v-hover v-slot="{ isHovering, props }">
        <v-card
            v-bind="props"
            :elevation="isHovering ? 10 : 2"
            :style="isHovering ? 'transform: scale(1.02);' : ''"
            :disabled="loading"
            :loading="loading"
            class="mx-2 my-12 transition"
            width="400"
            :color="'grey-lighten-3'"
            :variant="'flat'"
            @click="explore"
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
                height="200"
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

            <v-card-text class="text-area">
                <div>{{ description }}</div>
            </v-card-text>

            <!-- <v-divider class="mx-4 mb-1"></v-divider> -->
            <!-- <v-card-actions>
                <v-btn
                    color="deep-purple-lighten-2"
                    text="Explore"
                    block
                    border
                    @click="explore"
                ></v-btn>
            </v-card-actions> -->
        </v-card>
    </v-hover>
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
.text-area{
    height: 130px;
}
.transition {
  transition: all 0.3s ease;
}
</style>