<template>
    <v-dialog
        v-model="dialog"
        width="auto"
    >
        <v-sheet
            class="pa-4 text-center mx-auto"
            elevation="12"
            min-width="600"
            rounded="lg"
            width="100%"
        >
            <v-icon
                v-show="downloadZipProgressValue==100"
                class="mb-5"
                color="success"
                icon="mdi-check-circle"
                size="112"
                ></v-icon>
            <v-progress-circular
                v-show="downloadZipProgressValue!==100"
                :model-value="downloadZipProgressValue"
                :rotate="-90"
                :size="100"
                :width="15"
                color="primary"
                >
                {{ downloadZipProgressValue }}
            </v-progress-circular>

            <h2 class="text-h5 mb-6">{{ description }}</h2>

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
import { watch, ref } from 'vue';

const props = defineProps({
    downloadZipProgressValue:Number
})
const description = ref('Downloading dataset from DigitalTWINS Platform')

const dialog = defineModel("downloadDialog")


watch(()=>props.downloadZipProgressValue,(newVal, oldVal)=>{
    if(newVal==100){
        description.value = "Successfully download the dataset"
    }else{
        description.value = "Downloading dataset from DigitalTWINS Platform"
    }
})


</script>

<style scoped>

</style>