<template>
    <div class="col-style pa-3">
        <h2 class="w-100 text-center">
            {{ title }}
        </h2>
    
        <slot name="header"></slot>
        <v-divider></v-divider>

        <div class="mt-2 overflow-y-auto content">
            <Dialog
                v-for="(item, i) in items"
                :key="i"
                :min="1200"
                :btnText="item"
                :btn-height="'70px'"
                btnColor="#fff"
                btnVariant="tonal"
                save-btn-name="Close"
                @on-open="$emit('open')"
                @on-save="$emit('save')"
            >
                <template #title>
                    <h2 class="text-h5 mb-6">{{ title }}: {{ item }}</h2>
                </template>
                <template #description>
                    <slot name="dialog-description" :item="item"></slot>
                </template>
                <CWLViewer :cwl-path="cwlPathFn(item)" @on-workflow-loaded="(data: any) => $emit('workflow-loaded', data)" />
            </Dialog>
        </div>
    </div>
</template>

<script setup lang="ts">
import Dialog from '@/components/common/Dialog.vue';
import CWLViewer from '@/components/common/CWLViewer.vue';

defineProps<{
    title: string;
    items: string[];
    cwlPathFn: (item: string) => string;
}>();

defineEmits(['open', 'save', 'workflow-loaded']);
</script>

<style scoped>
.col-style {
    flex: 1;
    height: 100%;
    background: rgba(173, 216, 230, 0.4);
    border-radius: 15px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #fff;
    font-size: 1.2rem;
}
.content {
    height: calc(100% - 60px);
}
</style>
