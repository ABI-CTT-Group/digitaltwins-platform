<template>
    <v-dialog
      v-model="dialog"
      width="auto"
      @after-leave="handleDialogCancel"
    >
        <v-sheet
            class="pa-4 text-center mx-auto sheet bg-grey-darken-4"
            elevation="12"

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
                <slot name="title"></slot>
            </div>

                <slot name="description"></slot>

                <v-divider class="mb-4"></v-divider>
                
                <slot></slot>

                <div class="text-end">
                <v-btn
                    class="text-none hover-animate"
                    color="success"
                    variant="tonal"
                    width="90"
                    :rounded="btnRounded"
                    @click="handleDialogSave"
                >
                    {{ saveBtnName }}
                </v-btn>
            </div>
        </v-sheet>
    </v-dialog>

    <div class="px-2 my-6">
      <v-btn
        v-show="showDialog"
        :color="btnColor"
        :prepend-icon="btnIcon"
        :height="btnHeight"
        class="hover-animate"
        max-width="100"
        block
        :text="btnText" 
        :variant="btnVariant"
        :rounded="btnRounded"
        @click="openDialog"
      ></v-btn>
    </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

interface DialogProps {
    max?: number;
    min?: number;
    icon?: string;
    btnText?: string;
    btnColor?: string;
    btnIcon?: string;
    btnVariant?: "outlined" | "flat" | "text" | "elevated" | "tonal" | "plain" | undefined;
    showDialog?: boolean;
    saveBtnName?: string;
    btnHeight?:string;
    btnRounded?:string;
}

withDefaults(defineProps<DialogProps>(), {
    max: 600,
    min: 600,
    icon: "mdi-cog-outline",
    btnText: "",
    btnColor: "",
    btnIcon: "",
    btnVariant: "outlined",
    showDialog: true,
    saveBtnName: "Save",
    btnHeight:"",
    btnRounded:"lg"
});

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
.sheet{
    width: 80dvw !important;
    font-family: "Nunito", sans-serif;
    font-optical-sizing: auto;
    font-weight: 400;
    font-style: normal;
    background: rgba(0, 0, 0, 0.6) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    box-shadow:
        0 10px 30px rgba(0, 0, 0, 0.5),
        inset 0 0 8px rgba(255, 255, 255, 0.05);
    color: #f0f3f8;
    padding: 28px;
}
</style>