<template>
    <v-dialog
        v-model="dialog!"
        width="auto"
    >
        <v-sheet
            class="pa-4 text-center mx-auto"
            elevation="12"
            min-width="600"
            rounded="lg"
            width="100%"
        >
            <v-progress-circular
                v-show="submitState == 'waiting'"
                :size="70"
                :width="7"
                color="purple"
                indeterminate
                ></v-progress-circular>
            <v-icon
                v-show="submitState == 'true'"
                class="mb-5"
                color="success"
                icon="mdi-check-circle"
                size="112"
                ></v-icon>
            <v-icon
                v-show="submitState == 'false'"
                class="mb-5"
                color="error"
                icon="mdi-close-outline"
                size="112"
                ></v-icon>
            <h2 v-show="submitState == 'waiting'" class="text-h5 my-6 ">Submitting dataset to DigitalTWINS Platform</h2>
            <h2 v-show="submitState == 'true'" class="text-h5 my-6">Successfully submitted dataset to DigitalTWINS Platform</h2>
            <h2 v-show="submitState == 'false'" class="text-h5 my-6">Failed to submit dataset to DigitalTWINS Platform</h2>
            <v-divider class="mb-4"></v-divider>

            <div class="text-end">
            <v-btn
                class="text-none"
                color="success"
                variant="flat"
                width="90"
                rounded
            >
                Done
            </v-btn>
            </div>
        </v-sheet>
    </v-dialog>
    
</template>

<script setup lang="ts">
import { ref, onBeforeMount} from 'vue';
const props = defineProps({
    submitState:String
})

const dialog = defineModel("submitDialog")


</script>

<style scoped>

</style>