<template>
    <!-- <v-hover
        v-slot="{ isHovering, props }"
        open-delay="200"
      > -->
        <v-card
            :loading="loading"
            class="w-75 ma-4 card-color"
            color="grey-darken-1"
        >
            <v-card-text>
                <div class="d-flex justify-space-between align-center mb-4">
                    <div class="title font-weight-black text-grey-lighten-3">{{ data.name }}</div>
                    <div v-if="data.category === 'Assays'" class="d-flex align-center">
                        <v-icon
                            icon="mdi-border-radius"
                            color="grey"
                            class="hover-animate cursor-pointer"
                            @click="handleAssayExpandClicked(data.seekId, data.name)"
                            ></v-icon>
                    </div>
                </div>

            <div class="description text-medium-emphasis text-grey-darken-3">
                {{ data.description }}
            </div>
            </v-card-text>

            <v-card-actions class="d-flex justify-space-between px-10">
                <slot name="action"></slot>
                <v-btn
                    v-show="data.category !== 'Assays'"
                    color="pink-darken-2"
                    text="Explore"
                    variant="tonal"
                    rounded="md"
                    class="hover-animate"
                    @click.once = "handleExploreClicked(data.seekId, data.name, data.category, data.description)"
                ></v-btn>
                <Dialog
                    :showDialog="data.category === 'Assays' && !isClinicianView"
                    :min="1200"
                    btnText="Edit"
                    btnColor = "deep-orange"
                    btnVariant="tonal"
                    btnRounded="md"
                    @on-open = "handleAssayEditClicked(data.seekId, data.name)"
                    @on-save= "handleAssaySave"
                >
                    <template #title>
                        <h2 class="dialog-title mb-6">Update Assay <span class="dialog-title-name" >"{{ data.name }}"</span> </h2>
                    </template>
                    <template #description>
                        <p class="mb-4 dialog-description">
                            Config the assay's: workflow, dataset and cohorts. 
                            <br/>
                            Click `Save` button to save your configurations. Click grey area to cancel.
                        </p>
                    </template>
                    <AssayContent v-model="currentAssayDetails" />
                </Dialog>

                <div  v-if="data.category === 'Assays'">
                    <AssayBasicCardButtons
                        :assay-seek-id="data.seekId"
                        :category="data.category"
                        @assay-launch-clicked="handleAssayLaunchClicked"
                        @assay-monitor-clicked="handleAssayMonitorClicked"
                        @assay-verify-clicked="handleAssayVerifyClicked"
                        @assay-download-clicked="handleAssayDownloadClicked"
                        @assay-upload-clicked="handleAssayUploadClicked"/>
                </div>
            </v-card-actions>
        </v-card>
    <!-- </v-hover> -->
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { IDashboardCategory } from '@/models/apiTypes';
import Dialog from '@/components/commonBar/Dialog.vue';
import AssayContent from '@/components/dt-components/AssayContent.vue';
import AssayBasicCardButtons from './AssayBasicCardButtons.vue';
import { storeToRefs } from "pinia";
import { useDashboardPageStore } from '@/store/states';

const {
    assayExecute, 
    allAssayDetailsOfStudy, 
    currentAssayDetails,
    isClinicianView
 } = storeToRefs(useDashboardPageStore());

 const loading = ref(false);

const props = withDefaults(defineProps<{
    data: IDashboardCategory,
}>(),{
    data: () => ({ } as IDashboardCategory)
});

const emit = defineEmits(["ExpandClicked", "ExploreClicked", "AssayEditClicked", "AssaySave", "AssayLaunchClicked", "AssayMonitorClicked", "AssayVerifyClicked", "AssayDownloadClicked", "AssayUploadClicked"]);

const handleAssayExpandClicked = (seekId: string, name: string) => {
    emit("ExpandClicked", seekId, name);
};
const handleAssayEditClicked = (seekId: string, name: string) => {
    emit("AssayEditClicked", seekId, name);
};
const handleAssaySave = () => {
    emit("AssaySave");
};
const handleExploreClicked = (seekId: string, name: string, category: string, description: string) => {
    emit("ExploreClicked", seekId, name, category, description);
};
const handleAssayLaunchClicked = (seekId: string) => {
    loading.value = true;
    emit("AssayLaunchClicked", seekId);
    setTimeout(() => {
        loading.value = false;
    }, 10000);
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
.card-color {
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(0,0,0,0.45) 100%), radial-gradient(at top center, rgba(255,255,255,0.30) 0%, rgba(0,0,0,0.60) 120%) #000; background-blend-mode: multiply,multiply;
    background-color: transparent !important;
}
.title{
    font-size: 1.1rem;
    line-height: 1.2;
}
.description{
    font-size: 0.7rem;
    line-height: 1.4;
}
</style>