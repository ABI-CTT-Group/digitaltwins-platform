<template>
    <div class="container d-flex flex-column align-center">
        <div class="position-fixed breadcrumbs d-flex justify-start align-center w-66">
            <v-breadcrumbs
                class="custom-pointer font-weight-black"
                :items="breadCrumbsItems"
                divider="/"
                @click="handleBreadCrumbsClick"
            ></v-breadcrumbs>
        </div>
        <div>
            <HelpIcon class="position-fixed dashboard-title" :size="50" @click="handleHelpClick"/>
        </div>
        <v-card v-if="currentCategory !== 'Programmes' && currentCategory !== ''" class="position-fixed intro d-flex flex-column overflow-y-auto justify-space-around pa-5" color="transparent">
            <v-card-text>
                <div v-for="c in detailsRenderItems.categories" :key="c.name" class="text-grey-lighten-3 my-2 d-flex flex-row align-center">
                    <span  class="tooltip-title d-flex justify-center">
                        <v-icon
                            color="blue-darken-1"
                            icon="mdi-information-outline"
                            class="mx-1"
                            size="small"
                            ></v-icon>
                        <v-tooltip
                            activator="parent"
                            location="bottom"
                            max-width="300"
                        >
                            {{ c.description }}
                        </v-tooltip>
                        {{ c.category === 'Studies' ? 'Study' : c.category.slice(0,-1) }}
                    </span>
                    <span class="tooltip-panel mx-3">
                        {{c.name}}
                    </span>
                </div>
            </v-card-text>
        </v-card>

        <div  class="basic-card-container w-100 d-flex flex-column justify-center align-center ">
            <div class="w-75 d-flex flex-wrap px-6 mt-10 justify-center align-center overflow-y-auto">
                <AssayBasicCard v-for="data in currentCategoryData"
                            :key="data.name"
                            :data="data"
                            :is-clinician-view="isClinicianView"
                            @expand-clicked="handleAssayExpandClicked"
                            @explore-clicked="handleExploreClicked"
                            @assay-edit-clicked="handleAssayEditClicked"
                            @assay-save="handleAssaySave"
                            @assay-launch-clicked="handleAssayLaunchClicked"
                            @assay-monitor-clicked="handleAssayMonitorClicked"
                            @assay-verify-clicked="handleAssayVerifyClicked"
                            @assay-download-clicked="handleAssayDownloadClicked"
                            @assay-upload-clicked="handleAssayUploadClicked">
                </AssayBasicCard>
            </div>
        </div>
        <DownloadSheet :download-zip-progress-value="downloadZipProgressValue" v-model:download-dialog="downloadDialog"></DownloadSheet>
        <SubmitSheet v-model:submit-dialog="submitDialog" :submit-state="submitState" />
    </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { IDashboardCategory } from '@/models/types';
import { useDashboardView } from '@/composables/useDashboardView';
import AssayBasicCard from '@/components/domain/AssayBasicCard.vue';
import DownloadSheet from '@/components/domain/DownloadSheet.vue';
import SubmitSheet from '@/components/domain/SubmitSheet.vue';
import HelpIcon from '@/components/common/HelpIcon.vue';

const {
    isClinicianView,
    currentCategory,
    currentCategoryData,
    breadCrumbsItems,
    detailsRenderItems,
    downloadZipProgressValue,
    downloadDialog,
    submitDialog,
    submitState,
    handleBreadCrumbsClick,
    handleAssayEditClicked,
    handleAssaySave,
    handleAssayLaunchClicked,
    handleAssayMonitorClicked,
    handleAssayVerifyClicked,
    handleAssayDownloadClicked,
    handleAssayUploadClicked,
    handleAssayExpandClicked,
    handleExploreClicked,
    handleHelpClick,
    initDashboard,
} = useDashboardView(true);

onMounted(() => initDashboard((item: IDashboardCategory) => item.name === 'Auckland hospital'));
</script>

<style scoped>
.breadcrumbs {
    top: 110px;
    border-radius: 10px;
    box-shadow:  6px 6px 20px  #0e3f5a,
                -6px -6px 20px #0b2433;
}
.custom-pointer {
  cursor: pointer !important;
}

.intro{
    top: 30%;
    left: 5px;
    width: 20%;
}
.basic-card-container{
    height: 95dvh;
    padding-top: 150px;
}
.tooltip-title{
     cursor: help;
    font-weight: 800;
    color: coral;
}
.tooltip-panel{

    font-size: 0.8rem;
    line-height: 1.2;
}
.dashboard-title{
    top: 100px;
    right: 35px;
    max-width: 10dvw;
}
</style>
