<template>
    <v-dialog
      v-model="dialog"
      width="auto"
      @after-leave="handleDialogCancel"
    >
        <v-sheet
            class="pa-4 text-center mx-auto"
            elevation="12"
            min-width="600"
            max-width="600"
            rounded="lg"
            width="100%"
        >
            <div class="d-flex justify-space-start align-center">
                <v-icon
                class="mb-5 mr-4"
                color="success"
                icon="mdi-cog-outline"
                size="60"
                ></v-icon>

                <h2 class="text-h5 mb-6">Keyboard Settings</h2>
            </div>
                

                <p class="mb-4 text-medium-emphasis text-body-2">
                    Customize your keyboard shortcuts for Tumour Study Tool. 
                    <br/>
                    Click `Save` button to save your changes. Click grey area to cancel.
                </p>

                <v-divider class="mb-4"></v-divider>

                <slot></slot>

                <div class="text-end">
                <v-btn
                    class="text-none"
                    color="success"
                    variant="flat"
                    width="90"
                    rounded
                    @click="handleDialogSave"
                >
                    Save
                </v-btn>
            </div>
        </v-sheet>
    </v-dialog>

    <div class="px-2 my-6">
      <v-btn
        color="deep-orange"
        prepend-icon="mdi-cog"
        block
        density="comfortable"
        size="small"
        text="Keyboard Settings"
        @click="openDialog"
      ></v-btn>
    </div>
</template>

<script setup lang="ts">
import { ref, defineEmits } from "vue";

const dialog = ref(false);
const isSaved = ref(false);
const emit = defineEmits([
    "onOpen",
    "onCancel",
    "onSave"
]);

const openDialog = () => {
    dialog.value = true;
    isSaved.value = false;
    emit("onOpen");
}

const handleDialogCancel = () => {
    if(isSaved.value) return;
    emit("onCancel");
    dialog.value = false;
}

const handleDialogSave = () => {
    dialog.value = false;
    isSaved.value = true;
    emit("onSave");
}
</script>

<style scoped>

</style>