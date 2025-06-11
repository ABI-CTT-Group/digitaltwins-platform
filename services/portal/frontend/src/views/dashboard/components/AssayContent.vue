<template>
    <div class="border-sm py-2 my-5 mx-5 d-flex flex-column align-start">
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25 mt-4">Workflow: </span>
            <div class="w-66">
                <v-select
                    v-model="assayDetails!.workflow.seekId"
                    label="Select Workflow"
                    :items="workflowRenderItems"
                    item-title="name"
                    item-value="seekId"
                    variant="outlined"
                    @update:model-value="handleWorkflowSelected"
                ></v-select>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25">Inputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="data in assayDetails!.workflow.inputs">
                    <span class="text-subtitle-2 w-25">{{ data.input.name.replaceAll("_", " ") }}:</span>
                    <div class="w-50 mx-1">
                        <v-select
                            v-model="data.datasetSelectedUUID"
                            :label="`Select ${ data.input.category } Dataset`"
                            :items="!!workflowInputDatasetSamples[data.input.name]?workflowInputDatasetSamples[data.input.name].datasetRenderItems:[]"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            @update:model-value="(value)=>handleDatasetSelected(value, data.input.name, data.input.category)"
                        ></v-select>
                    </div>
                    <div class="w-50 mx-1">
                        <v-select
                            v-if="data.input.category === 'measurement'"
                            v-model="data.sampleSelectedType"
                            label="Sample Type"
                            :items="!!workflowInputDatasetSamples[data.input.name]?workflowInputDatasetSamples[data.input.name].selectedDatasetSampleTypes:[]"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            @update:model-value="handleSampleSelected(data.input.name)"
                        ></v-select>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25">Outputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="data in assayDetails!.workflow.outputs">
                    <span class="text-subtitle-2 w-25">{{ data.output.name.replaceAll("_", " ") }}:</span>
                    <div class="w-50 mx-1">
                        <v-text-field
                            v-model:model-value="data.datasetName"
                            label="Dataset Name"
                            clearable
                        ></v-text-field>
                    </div>
                    <div class="w-50 mx-1">
                        <v-text-field
                            v-model:model-value="data.sampleName"
                            label="Sample Name"
                            clearable
                        ></v-text-field>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25 mt-4">Cohorts:</span>
            <v-responsive
                class=""
                max-width="344"
            >
                <v-text-field
                v-model:model-value="assayDetails!.numberOfParticipants"
                :rules="[rules.required]"
                label="Number of Participants"
                clearable
                ></v-text-field>
        </v-responsive>
        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, watch, onMounted, onBeforeMount } from 'vue';
import { datasetsData } from "../mockData";
import { IWorkflowData } from '@/models/uiTypes';
import {IAssayDetails} from '@/models/apiTypes';
import { useDashboardGetDatasets, useDashboardSelectedDatasetSampleTypes } from '@/plugins/dashboard_api';
import { useDashboardWorkflowsStore, useDashboardWorkflowDetailStore } from '@/store/dashboard_store';
import { storeToRefs } from "pinia";


interface IItem {
    seekId: string;
    uuid: string;
    name: string;
}

interface IRenderWorkflowInputDatasetSamples {
    [key: string]: {
        category: string;
        datasetRenderItems: {
            uuid: string;
            name: string;
            sampleTypes: string[];
        }[];
        selectedDatasetSampleTypes: string[];
    }
}

const workflowRenderItems = ref<IItem[]>();
// const inputRenderItems = ref<IInput[]>([]);
// const outputRenderItems = ref<IOutput[]>([]);
const datasetRenderItems = ref<string[]>();
const { dashboardWorkflows } = storeToRefs(useDashboardWorkflowsStore());
const { getDashboardWorkflows } = useDashboardWorkflowsStore();
const { dashboardWorkflowDetail } = storeToRefs(useDashboardWorkflowDetailStore());
const { getDashboardWorkflowDetail } = useDashboardWorkflowDetailStore();

const assayDetails = defineModel<IAssayDetails>();
const workflowInputDatasetSamples = ref<IRenderWorkflowInputDatasetSamples>({});

const rules = {
    required: (value: number) => {
        if (!value) {
            return 'This field is required';
        }else if (isNaN(value)) {
            return 'Please enter a valid number';
        }
        else if (value < 1) {
            return 'Number of cohorts should be greater than 0';
        }else if (value % 1 !== 0) {
            return 'Number of cohorts should be an integer';
        }else {
            return true;
        }
    }
};

onBeforeMount(()=>{
    console.log("on before mount: ", );
    
})

onMounted(async () => {
    await getDashboardWorkflows();
    workflowRenderItems.value = dashboardWorkflows.value!.map(workflow => {
        return {
            seekId: workflow.seekId,
            uuid: workflow.uuid,
            name: workflow.name + " - " + workflow.type
        }
    });
    
    if(!!String(assayDetails.value?.workflow.seekId)){
        await getDashboardWorkflowDetail(String(assayDetails.value?.workflow.seekId));
        dashboardWorkflowDetail.value!.inputs!.map( (input) => {
            workflowInputDatasetSamples.value[input.name] = { category: input.category, datasetRenderItems: [], selectedDatasetSampleTypes: [] };
        });
        for(let key in workflowInputDatasetSamples.value) {
            const datasets = await getDatasets(workflowInputDatasetSamples.value[key].category);
            workflowInputDatasetSamples.value[key].datasetRenderItems = datasets.map(dataset => {
                return { uuid: dataset.uuid, name: dataset.name, sampleTypes: [] };
            });
            const inputData = assayDetails.value!.workflow.inputs.find(data => {
                if (data.input.name === key) {
                    return data
                }
            });
            if(inputData?.input.category === "measurement"){
                workflowInputDatasetSamples.value[key].selectedDatasetSampleTypes = await useDashboardSelectedDatasetSampleTypes(inputData.datasetSelectedUUID);
                
            }else{
                workflowInputDatasetSamples.value[key].selectedDatasetSampleTypes = [];
            }
            
        }
    }
    
});

const handleWorkflowSelected = async (value: string) => {
    await getDashboardWorkflowDetail(value);
    assayDetails.value!.workflow.inputs = dashboardWorkflowDetail.value!.inputs!.map( (input) => {
        workflowInputDatasetSamples.value[input.name] = { category: input.category, datasetRenderItems: [], selectedDatasetSampleTypes: [] };
        return { input, datasetSelectedUUID: "", sampleSelectedType: "" };
    });
    for(let key in workflowInputDatasetSamples.value) {
        const datasets = await getDatasets(workflowInputDatasetSamples.value[key].category);
        workflowInputDatasetSamples.value[key].datasetRenderItems = datasets.map(dataset => {
            return { uuid: dataset.uuid, name: dataset.name, sampleTypes: [] };
        });
    }
    assayDetails.value!.workflow.outputs = dashboardWorkflowDetail.value!.outputs!.map(output => {
        return { output, datasetName: "New Dataset 1", sampleName: output.name };
    });
};


const handleDatasetSelected = async (value: string, inputName:string, inputCategory:string) => {
    let sampleTypes:string[] = []
    if(inputCategory === "measurement") {
        sampleTypes = await useDashboardSelectedDatasetSampleTypes(value);
        workflowInputDatasetSamples.value[inputName].selectedDatasetSampleTypes = sampleTypes;
    }
    
    assayDetails.value!.workflow.inputs.find(data => {
        if (data.datasetSelectedUUID === value && data.input.name === inputName) {
            data.sampleSelectedType = "";
        }
    })
    
};

const handleSampleSelected = (value: any) => {
    console.log(value);
};


const findWorkflow = (workflow: string) => {
    const workflowName = workflow.split("-")[0];
    const workflowType = workflow.split("-")[1];
    return dashboardWorkflows.value!.find(workflow => workflow.name === workflowName && workflow.type === workflowType);
};

const getDatasets = async (workflowCategory:string) => {
    const datasets = await useDashboardGetDatasets(workflowCategory);
    return datasets;
};

</script>

<style scoped>
.fancy-shadow {
    border-radius: 6px;
    background: linear-gradient(145deg, #242323, #1e1e1e);
    box-shadow:  1px 1px 5px #d3d3d3,
                -1px -1px 5px #ededed;
}
</style>