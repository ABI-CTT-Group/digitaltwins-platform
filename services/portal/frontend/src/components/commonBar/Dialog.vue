<template>
    <v-dialog
      v-model="dialog"
      width="auto"
      @after-leave="handleDialogCancel"
    >
        <v-sheet
            class="pa-4 text-center mx-auto"
            elevation="12"
            :min-width="min"
            :max-width="max"
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
                    class="text-none"
                    color="success"
                    variant="flat"
                    width="90"
                    rounded
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
        max-width="100"
        block
        :text="btnText" 
        :variant="btnVariant"
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
    btnVariant?: string;
    showDialog?: boolean;
    saveBtnName?: string;
    btnHeight?:string;
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
    btnHeight:""
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

</style>