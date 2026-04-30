<template>
    <v-container class="d-flex justify-center align-center h-100 w-100">
        <v-row>
            <v-col cols="12" md="6" class="d-flex justify-center align-center">
                <CatalogueColumn
                    title="Workflows"
                    :items="workflows"
                    :cwlPathFn="(item) => `/eps/workflows/${item}.cwl`"
                    @workflow-loaded="handleWorkflowLoaded"
                >
                    <template #header>
                        <Dialog
                            :min="1200"
                            btnText="New Workflow +"
                            btnColor="#5865f2"
                            btnVariant="flat"
                            save-btn-name="Close"
                        >
                            <template #title>
                                <h2 class="text-h5 mb-6">Workflow Assembler</h2>
                            </template>
                            <template #description>
                                <div class="d-flex justify-center w-100 pa-3">
                                    <div class="w-75">
                                        <v-img :aspect-ratio="1" max-height="600" src="/eps/workflows/new_workflow.png"></v-img>
                                    </div>
                                </div>
                            </template>
                        </Dialog>
                    </template>
                    <template #dialog-description="{ item }">
                        <div class="d-flex justify-center w-100 pa-3">
                            <div class="w-100">
                                <CWLWorkflowViewer :workflow="workflowData"/>
                            </div>
                        </div>
                    </template>
                </CatalogueColumn>
            </v-col>
            <v-col cols="12" md="6" class="d-flex justify-center align-center">
                <CatalogueColumn
                    title="Tools"
                    :items="tools"
                    :cwlPathFn="(item) => `/eps/tools/all/${item}.cwl`"
                />
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useDashboardWorkflows } from "@/bootstrap/dashboard_api";
import { DashboardWorkflow } from "@/models/types";
import Dialog from '@/components/common/Dialog.vue';
import CWLWorkflowViewer from '@/components/domain/workflow/CWLWorkflowViewer.vue';
import CatalogueColumn from './components/CatalogueColumn.vue';

const dashboardWorkflows = ref<DashboardWorkflow[]>();
const getDashboardWorkflows = async () => {
    dashboardWorkflows.value = await useDashboardWorkflows();
};
const workflowData = ref({});

// TODO: switch to API once /dashboard/workflows returns full set
const workflows = ref([
    "Automated torso model generation – script", 
    "Tumour position selection - GUI",
    "Automated tumour position reporting – script",
    "Electrode selection - script",
    "Quantification of frequency of electrical... - script",
    "Statistical analysis of electrode measurements - script",
    "Generate personalised model - script",
    "Quantify scapulothoracic and... - script",
    "Generate personalised anatomical model of lung - script",
    "Identify under perfused regions - script",
    "Identify remodelling level - script",
    "Predict post surgery PAP - script"
]);

// TODO: https://github.com/ABI-CTT-Group/DigitalTWINS-Portal/issues/xxx switch to API
const tools = ref([
    "baseline_perfusion_simulation_1d_cfd",
    "centreline_annotation",
    "convert_ex_to_ip_ex2ip",
    "create_seed_points",
    "flow_intensity_analysis_and_comparison_to_baseline",
    "grow_into_clusters",
    "intensity_mapping_and_clustering",
    "run_post_pea_prediction",
    "run_remodelling_disease",
    "extract_clinical_measurements",
    "burst_duration",
    "frequency_analysis",
    "load_dataset_summary_data",
    "load_file_into_matlab_script",
    "open_gems_and_load_experiment_file",
    "paper_figure",
    "plot_summary_statistics",
    "ploting_figures_for_publication",
    "propagation_speed",
    "respiration_filtering",
    "create_mesh",
    "create_nifti",
    "create_point_cloud",
    "segment"
]);

onMounted(async ()=>{
     
})

const handleWorkflowLoaded = (data: any) => {
    console.log("CWL Data Loaded: ", data);
    workflowData.value = data;
}
</script>