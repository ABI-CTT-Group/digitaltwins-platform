<template>
    <div class="border-sm py-2 my-5 mx-5 d-flex flex-column align-start">
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25 mt-4">Workflows Configurations: </span>
            <div class="w-50">
                <v-select
                    v-model="selectedWorkflow"
                    label="Select Workflow"
                    :items="workflowRenderItems"
                    variant="outlined"
                ></v-select>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25">Inputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="input in inputRenderItems">
                    <span class="text-subtitle-2 w-25">{{ input.name }}:</span>
                    <div class="w-50 mx-1">
                        <v-select
                            v-model="input.datasetSelected"
                            label="Select Dataset"
                            :items="datasetsData"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            @update:model-value="(value)=>handleDatasetSelected(value, input.name)"
                        ></v-select>
                    </div>
                    <div class="w-50 mx-1">
                        <v-select
                            v-model="input.sampleSelected"
                            label="Select Sample"
                            :items="input.sampleRenderItems"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            @update:model-value="handleSampleSelected(input.name)"
                        ></v-select>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25">Outputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="output in outputRenderItems">
                    <span class="text-subtitle-2 w-25 fancy-shadow">{{ output }}</span>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 w-100">
            <span class="text-subtitle-2 w-25 mt-4">Cohorts:</span>
        </div>
    </div>
</template>

<script setup lang="ts">

import { ref, watch, onMounted } from 'vue';
import { datasetsData } from "../mockData";
import { IWorkflowData } from '@/models/uiTypes';

interface IInput {
    name: string;
    datasetSelected: string;
    sampleSelected: string;
    sampleRenderItems: {
        uuid: string;
        name: string;
    }[];
}

const props = defineProps<{
    workflowsData: IWorkflowData[];
}>();

const workflowRenderItems = ref<string[]>();
const inputRenderItems = ref<IInput[]>([]);
const outputRenderItems = ref<string[]>([]);
const datasetRenderItems = ref<string[]>();
const selectedWorkflow = ref<string>("");


onMounted(() => {
    workflowRenderItems.value = props.workflowsData.map(workflow => workflow.name + "-" + workflow.type);
});


watch(() => selectedWorkflow.value, (value) => {
    const workflow = findWorkflow(value);
    inputRenderItems.value = workflow!.inputs.map(input => {
        return { name: input, datasetSelected: "", sampleSelected: "", sampleRenderItems: [] };
    });
    const datasets = getDatasets();
    datasetRenderItems.value = datasets.map(dataset => dataset.name);
    outputRenderItems.value = workflow!.outputs;
});

const handleDatasetSelected = (value: string, name:string) => {
    const dataset = datasetsData.find(dataset => dataset.uuid === value);
    inputRenderItems.value.find(input => {
        if (input.datasetSelected === value && input.name === name) {
            input.sampleSelected = "";
            input.sampleRenderItems = dataset!.samples;
        }
    })
    
};

const handleSampleSelected = (value: any) => {
    console.log(value);
};


const findWorkflow = (workflow: string) => {
    const workflowName = workflow.split("-")[0];
    const workflowType = workflow.split("-")[1];
    return props.workflowsData.find(workflow => workflow.name === workflowName && workflow.type === workflowType);
};

const getDatasets = () => {
    return datasetsData;
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