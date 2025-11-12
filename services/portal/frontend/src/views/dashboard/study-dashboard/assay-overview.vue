<template>
    
    
    <div v-if="assayReadyToLaunch" class="container d-flex justify-center">
        <BackIcon/>
        <div class="overflow-y-auto sub-container d-flex flex-column align-center no-select">
            <v-container fluid class="py-10">
                <v-row justify="center">
                    <v-col cols="12" md="10">
                        <div class="plugin-title">
                          <h1>Assay Report Center</h1>
                          <h3 v-if="!!seekAssay" class="subtitle">Assay: {{ seekAssay?.name }}</h3>
                          <p v-else class="subtitle">Integrate your clinical tools, workflows, and datasets seamlessly</p>

                        </div>
                        <div class="function-button mb-10 w-75">
                          
                          <AssayBasicCardButtons
                            :assay-seek-id="assayId"
                            category="assay"
                            @assay-launch-clicked="handleAssayLaunchClicked"
                            @assay-monitor-clicked="handleAssayMonitorClicked"
                            @assay-verify-clicked="handleAssayVerifyClicked"
                            @assay-download-clicked="handleAssayDownloadClicked"
                            @assay-upload-clicked="handleAssayUploadClicked"/>
                        </div>

                        <v-card class="pa-6 mb-10 " elevation="4">
                          <h2 class="pipeline-title font-weight-medium mb-4">Cohorts</h2>
                          <div class="overflow-y-auto" style="height: 50vh;">
                              <v-row v-for="cohort in cohorts" :key="cohort.uuid" class="d-flex align-center px-10" no-gutters>
                                  <v-col cols="12" md="6">
                                    <p><strong>{{ capitalize(cohort.name) }}</strong> <span class="mx-2 px-2 rounded-sm bg-grey-darken-4 text-orange">{{ cohort.uuid }}</span></p>
                                  </v-col>
                                  <v-col cols="12" md="6" class="d-flex justify-center">
                                    <v-btn
                                    color="cyan"
                                    :text="'Get Report'"
                                    variant="tonal"
                                    :width="200"
                                    rounded="md"
                                    class="hover-animate ma-3"
                                    ></v-btn>
                                  </v-col>
                                  <v-divider :thickness="3"></v-divider>
                              </v-row>
                            </div>
                          
                        </v-card>
                    </v-col>
                </v-row>
            </v-container>
        </div>
    </div>
    <assay-overview-empty v-else/>
</template>

<script setup lang="ts">
import BackIcon from '@/components/commonBar/BackIcon.vue';
import { useRoute } from 'vue-router';
import { asyncComputed } from '@vueuse/core'
import { ref, computed, onMounted, onBeforeMount, watchEffect} from 'vue';
import { useDashboardPageStore } from '@/store/states';
import { useDashboardWorkflowDetail, useDashboardSeekAssay } from "@/plugins/dashboard_api";
import AssayOverviewEmpty from '@/components/dt-components/AssayOverviewEmpty.vue';
import AssayBasicCardButtons from '@/components/dt-components/AssayBasicCardButtons.vue';
import WorkflowStatusTag from '@/components/dt-components/workflow/WorkflowStatusTag.vue';
import { WorkflowStatus } from '@/components/dt-components/workflow/workflowStatus';
import { ISeekAssayDetails } from '@/models/apiTypes';
import { capitalize } from '@/utils/common';

import { storeToRefs } from "pinia";


const route = useRoute();

const { allAssayDetailsOfStudy } = storeToRefs(useDashboardPageStore());
const assayId = route.query.assayId as string;
const assayDetails = allAssayDetailsOfStudy.value[assayId];
const assayReadyToLaunch = ref(false);
const seekAssay = ref<ISeekAssayDetails>();
const assayPromise = useDashboardSeekAssay(assayId);
const cohorts = ref<Array<any>>([
  {name: "Cohort 1", id: "uuid-1"},
  {name: "Cohort 2", id: "uuid-2"},
  {name: "Cohort 3", id: "uuid-3"},
]);

onBeforeMount(async ()=>{
    assayReadyToLaunch.value = assayDetails?.isAssayReadyToLaunch || false;
    seekAssay.value = await assayPromise;
}) 
onMounted(() => {
  
});


const handleAssayUploadClicked = async (assay_seek_id:string) => {
  
}

const handleAssayDownloadClicked = async (assay_seek_id:string) => {
   
    
}

const handleAssayVerifyClicked = async (assay_seek_id:string) => {
    window.open("http://bn363773:8888/lab/tree/20250722_105946/verify.ipynb","_blank");
}

const handleAssayMonitorClicked = async (assay_seek_id:string) => {
}

const handleAssayLaunchClicked = async (assay_seek_id:string) => {
   
}

</script>

<style scoped>

.sub-container{
    width: 90%;
    margin-top: 70px ;
    padding: 20px;
}

.plugin-title {
  text-align: center;
  margin-bottom: 50px;
}

.plugin-title h1 {
  font-size: 3.2rem;
  font-weight: 800;
  background: linear-gradient(90deg, #00bcd4, #29b6f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 12px rgba(0, 188, 212, 0.4);
  margin-bottom: 10px;
}

.plugin-title .subtitle {
  font-size: 1.125rem;
  color: #90a4ae;
  letter-spacing: 0.5px;
  margin-top: 8px;
}

.v-card {
  background-color: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  color: #cfd8dc;
  box-shadow: 0 4px 24px rgba(0, 188, 212, 0.08);
}

.v-card-title {
  color: #29b6f6;
  font-weight: 600;
}

h1, h2 {
  color: #ffffff;
}

.v-icon {
  color: #00bcd4;
}

.v-list-item-title {
  font-weight: 500;
  color: #e0f7fa;
}

.v-list-item-subtitle {
  color: #90a4ae;
}
.v-list{
  background-color:  rgba(0, 0, 0, 0.3) !important;
  border-radius: 12px;
}

.tool-card {
  background-color: rgba(0, 0, 0, 0.6) !important;
}



.pipeline-title {
  font-weight: 600;
}
.no-select{
  user-select: none;
}

.function-button{
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 20px;
  margin: 0 auto;
}

</style>