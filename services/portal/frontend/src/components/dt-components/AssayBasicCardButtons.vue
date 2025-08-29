<template>
    <div class="d-flex ga-2 justify-center flex-wrap">
        <v-btn
            color="green"
            :text="'Launch'"
            variant="tonal"
            :width="100"
            rounded="md"
            class="hover-animate"
            :disabled="!allAssayDetailsOfStudy[assaySeekId]?.isAssayReadyToLaunch"
            @click.once = "handleAssayLaunchClicked(assaySeekId)"
        >
        </v-btn>
        <v-btn
            color="green"
            :text="'Monitor'"
            variant="tonal"
            :width="100"
            rounded="md"
            class="hover-animate"
            :disabled="!(category === 'Assays'&& !!assayExecute![assaySeekId] && assayExecute![assaySeekId].text === 'Monitor')"
            @click = "handleAssayMonitorClicked(assaySeekId)"
        >
        </v-btn>
        <v-btn
            color="green"
            :text="'Verify'"
            variant="tonal"
            :width="100"
            rounded="md"
            class="hover-animate"
            :disabled="!allAssayDetailsOfStudy[assaySeekId]?.isAssayReadyToLaunch"
            @click = "handleAssayVerifyClicked(assaySeekId)"
        ></v-btn>
        <v-btn
            color="green"
            :text="'Download'"
            variant="tonal"
            :width="100"
            rounded="md"
            class="hover-animate"
            :disabled="!allAssayDetailsOfStudy[assaySeekId]?.isAssayReadyToLaunch"
            @click = "handleAssayDownloadClicked(assaySeekId)"
        ></v-btn>
        <v-btn
            color="green"
            :text="'Submit'"
            variant="tonal"
            :width="100"
            rounded="md"
            class="hover-animate"
            :disabled="!allAssayDetailsOfStudy[assaySeekId]?.isAssayReadyToLaunch"
            @click = "handleAssayUploadClicked(assaySeekId)"
        ></v-btn>
    </div>
</template>

<script setup lang="ts">
import { IDashboardCategory } from '@/models/apiTypes';
import { storeToRefs } from "pinia";
import { useDashboardPageStore } from '@/store/states';

const {
    assayExecute, 
    allAssayDetailsOfStudy
 } = storeToRefs(useDashboardPageStore());
const props = withDefaults(defineProps<{
    assaySeekId: string;
    category: string;
    launchText?: string;
    monitorText?: string;
    verifyText?: string;
    downloadText?: string;
    uploadText?: string;
}>(),{
    launchText: "Launch",
    monitorText: "Monitor",
    verifyText: "Verify",
    downloadText: "Download",
    uploadText: "Submit"
});

const emit = defineEmits(["AssayLaunchClicked", "AssayMonitorClicked", "AssayVerifyClicked", "AssayDownloadClicked", "AssayUploadClicked"]);
const handleAssayLaunchClicked = (seekId: string) => {
    emit("AssayLaunchClicked", seekId);
};
const handleAssayMonitorClicked = (seekId: string) => {
    emit("AssayMonitorClicked", seekId);
};
const handleAssayVerifyClicked = (seekId: string) => {
    emit("AssayVerifyClicked", seekId);
};
const handleAssayDownloadClicked = (seekId: string) => {
    emit("AssayDownloadClicked", seekId);
};
const handleAssayUploadClicked = (seekId: string) => {
    emit("AssayUploadClicked", seekId);
};
</script>

<style scoped>

</style>