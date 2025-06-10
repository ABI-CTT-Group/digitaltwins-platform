<template>
    <v-row class="h-100 ">
        <v-col
            cols="12"
            md="6"
            class="d-flex justify-center align-center"
        >
            <div class="col-style  pa-3 overflow-y-auto">
                <h2 class="w-100 text-center">
                    Workflows
                </h2>
             
                <Dialog
                    :min="1200"
                    btnText="New Workflow +"
                    btnColor = "#5865f2"
                    btnVariant="flat"
                    save-btn-name="Close"
                    @on-open = "handleDialogOpen()"
                    @on-save= "handleDialogSave()"
                >
                    <template #title>
                        <h2 class="text-h5 mb-6">Workflow Assembler</h2>
                    </template>
                    <template #description>
                        <div class="d-flex justify-center w-100 pa-3">
                            <div class="w-75">
                                <v-img
                                    aspect-ratio="16/9"
                                    cover
                                    src="/eps/workflows/new_workflow.png"
                                ></v-img>
                            </div>
                        </div>
                    </template>
                </Dialog>
                <v-divider></v-divider>
                <div class="mt-2">
                    <Dialog
                        v-for="(workflow, i) in workflows"
                        :key="i"
                        :min="1200"
                        :btnText="workflow"
                        :btn-height="'100px'"
                        btnColor = "#5865f2"
                        btnVariant="outlined"
                        save-btn-name="Close"
                        @on-open = "handleDialogOpen()"
                        @on-save= "handleDialogSave()"
                    >
                        <template #title>
                            <h2 class="text-h5 mb-6">Workflow: {{ workflow }}</h2>
                        </template>
                        <template #description>
                            <div class="d-flex justify-center w-100 pa-3">
                                <div class="w-75">
                                    <v-img
                                        aspect-ratio="16/9"
                                        cover
                                        :src="`/eps/workflows/${workflow}.svg`"
                                    ></v-img>
                                </div>
                            </div>
                        </template>
                        <CWLViewer :cwl-path="`/eps/workflows/${workflow}.cwl`" />
                    </Dialog>
                </div>
            </div>
        </v-col>
        <v-col
            cols="12"
            md="6"
            class="d-flex justify-center align-center"
        >
             <div class="col-style overflow-y-auto pa-3">
                <h2 class="w-100 text-center">
                    Workflow tools
                </h2>

                <v-divider></v-divider>
                <div class="mt-2">
                    <Dialog
                        v-for="(tool, i) in tools"
                        :key="i"
                        :min="1200"
                        :btnText="tool"
                        :btn-height="'100px'"
                        btnColor = "#5865f2"
                        btnVariant="outlined"
                        save-btn-name="Close"
                        @on-open = "handleDialogOpen()"
                        @on-save= "handleDialogSave()"
                    >
                        <template #title>
                            <h2 class="text-h5 mb-6">Tool: {{ tool }}</h2>
                        </template>
                        <CWLViewer :cwl-path="`/eps/tools/all/${tool}.cwl`" />
                    </Dialog>
                </div>
            </div>
        </v-col>
    </v-row>

</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardWorkflowsStore } from "@/store/dashboard_store";
import Dialog from '@/components/commonBar/Dialog.vue';
import CWLViewer from '@/components/commonBar/CWLViewer.vue';

const { dashboardWorkflows } = storeToRefs(useDashboardWorkflowsStore());
const { getDashboardWorkflows } = useDashboardWorkflowsStore();
const isNewWorkflowClicked = ref(false)

const workflows = ref([
    "Automated torso model generation – script", 
    "Tumour position selection - GUI",
    "Automated tumour position reporting – script",
    "Electrode selection - script",
    "Quantification of frequency of electrical... - script",
    "Statistical analysis of electrode measurements - script",
    "EP2 workflow_1 - script",
    "EP2 workflow_2 - script",
    "EP1 workflow_1 - script",
    "EP1 workflow_2 - script",
    "EP1 workflow_3 - script",
    "EP1 workflow_4 - script"
]);

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
])

onMounted(async ()=>{
     
})

const handleDialogOpen = () => {

}

const handleDialogSave = () => {

}

</script>

<style scoped>
.col-style{
      flex:1;
      height: 75vh;
      background: rgba(173, 216, 230, 0.2);
      border-radius: 15px;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.18);
      color: #fff;
      font-size: 1.2rem;
}
</style>