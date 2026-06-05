<template>
    <v-form ref="formRef" class="py-2 my-5 mx-5 d-flex flex-column align-start" @submit.prevent>
        <div class="d-flex flex-row ma-2 workflow">
            <span class="assay-form-subtitle w-25 mt-4 accent-workflow">Workflow: </span>
            <div class="w-66 mt-4">
                <span class="workflow-name">{{ workflowDisplayName }}</span>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 input">
            <span class="assay-form-subtitle w-25 accent-input">Inputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="data in assayDetails!.workflow.inputs">
                    <span class="w-25">{{ capitalize(data.input.name.replaceAll("_", " ")) }}:</span>
                    <div class="w-50 mx-1">
                        <v-select
                            v-model="data.datasetSelectedUuid"
                            :label="`Select ${ capitalize(data.input.category) } Dataset`"
                            :items="!!workflowInputDatasetSamples[data.input.name]?workflowInputDatasetSamples[data.input.name].datasetRenderItems:[]"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            :rules="[v => !!v || 'Please select a dataset']"
                            @update:model-value="(value)=>handleDatasetSelected(value, data.input.name, data.input.category)"
                        ></v-select>
                    </div>
                    <div class="w-50 mx-1">
                        <v-select
                            v-if="data.input.category === 'measurement'"
                            v-model="data.sampleSelectedType"
                            label="Select Sample"
                            :items="!!workflowInputDatasetSamples[data.input.name]?workflowInputDatasetSamples[data.input.name].selectedDatasetSampleTypes:[]"
                            item-title="name"
                            item-value="uuid"
                            variant="outlined"
                            :rules="[v => !!v || 'Please select a sample type']"
                            @update:model-value="handleSampleSelected(data.input.name)"
                        ></v-select>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 output">
            <span class="assay-form-subtitle w-25 accent-output">Outputs: </span>
            <div class="w-75">
                <div class="w-75 d-flex flex-row mt-4" v-for="data in assayDetails!.workflow.outputs">
                    <span class="w-25">{{ capitalize(data.output.name.replaceAll("_", " ")) }}:</span>
                    <div class="w-50 mx-1">
                        <v-text-field
                            v-model:model-value="data.datasetName"
                            label="Enter Dataset Name"
                            clearable
                            :rules="[v => !!v?.trim() || 'Dataset name is required']"
                        ></v-text-field>
                    </div>
                    <div class="w-50 mx-1">
                        <v-text-field
                            v-model:model-value="data.sampleName"
                            label="Enter Sample"
                            clearable
                            :rules="[v => !!v?.trim() || 'Sample name is required']"
                        ></v-text-field>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex flex-row ma-2 cohort">
            <span class="assay-form-subtitle w-25 mt-4 accent-cohort">Cohorts:</span>
            <v-responsive
                class="my-2"
                max-width="444"
            >
                <v-text-field
                    v-model:model-value="cohortsParticipants"
                    @update:model-value="handleCohortUpdate"
                    class="py-3"
                    label="Enter Participants Ranges"
                    hint="Use commas and dashes, e.g. 1-5,6,7,9-15 (Ranges are inclusive)"
                    persistent-hint
                    :rules="[rules.cohort]"
                />
        </v-responsive>
        </div>
    </v-form>
</template>

<script setup lang="ts">

import { ref, watch, onMounted, onBeforeMount } from 'vue';
import {AssayDetails} from '@/models/types';
import { useDashboardGetDatasets, useDashboardSelectedDatasetSampleTypes, useDashboardWorkflowDetail } from '@/bootstrap/dashboard_api';

import { capitalize } from '@/utils/common';


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

const formRef = ref();
const cohortsParticipants = ref<string>("");
const datasetRenderItems = ref<string[]>();
const workflowDisplayName = ref<string>("");

const assayDetails = defineModel<AssayDetails>();
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
    },
    cohort:(value: string) => {
        const regex = /^\s*\d+\s*(-\s*\d+\s*)?(\s*,\s*\d+\s*(-\s*\d+\s*)?)*$/;
        if (!value) {
            return 'This field is required';
        } else if (!regex.test(value)) {
            return 'Invalid format. Use e.g. 1-5,6,7,9-15';
        } else if(!validateRangeFormat(value)){
            return 'Invalid range. Ensure that start of range is less than end.';
        } else {
            return true;
        }
    }
};

function validateRangeFormat(value:string) {

  const parts = value.split(',');
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.includes('-')) {
      const [start, end] = trimmed.split('-').map(Number);
      if (start >= end) return false;
    }
  }
  return true;
}

onBeforeMount(()=>{
})

onMounted(async () => {

    if (assayDetails.value?.numberOfParticipants?.length) {
        cohortsParticipants.value = compressRangeList(assayDetails.value.numberOfParticipants);
    }

    if (assayDetails.value?.workflow?.seekId) {
        const name = assayDetails.value.workflow.name;
        const type = assayDetails.value.workflow.type;
        if (name) {
            workflowDisplayName.value = type ? `${name} - ${type}` : name;
        } else {
            const workflowDetail = await useDashboardWorkflowDetail(assayDetails.value.workflow.seekId);
            workflowDisplayName.value = workflowDetail.type
                ? `${workflowDetail.name} - ${workflowDetail.type}`
                : workflowDetail.name;
        }
    }

    const inputs = assayDetails.value?.workflow.inputs ?? [];
    for (const inputData of inputs) {
        const { name, category } = inputData.input;
        const datasets = await getDatasets(category);
        const sampleTypes = category === "measurement" && inputData.datasetSelectedUuid
            ? await useDashboardSelectedDatasetSampleTypes(inputData.datasetSelectedUuid)
            : [];
        workflowInputDatasetSamples.value[name] = {
            category,
            datasetRenderItems: datasets.map(d => ({ uuid: d.uuid, name: d.name, sampleTypes: [] })),
            selectedDatasetSampleTypes: sampleTypes,
        };
    }
    
});

const handleDatasetSelected = async (value: string, inputName:string, inputCategory:string) => {
    let sampleTypes:string[] = []
    if(inputCategory === "measurement") {
        sampleTypes = await useDashboardSelectedDatasetSampleTypes(value);
        workflowInputDatasetSamples.value[inputName].selectedDatasetSampleTypes = sampleTypes;
    }
    
    assayDetails.value!.workflow.inputs.find(data => {
        if (data.datasetSelectedUuid === value && data.input.name === inputName) {
            data.sampleSelectedType = "";
        }
    })
    
};

const handleSampleSelected = (_value: any) => {
    // Selection is bound via v-model; no side-effect needed on change.
};

function compressRangeList(numbers: number[]): string {
  if (!numbers || numbers.length === 0) return "";

  const sorted = Array.from(new Set(numbers)).sort((a, b) => a - b);
  const ranges = [];
  let start = sorted[0];
  let end = sorted[0];

  for (let i = 1; i < sorted.length; i++) {
    const current = sorted[i];
    if (current === end + 1) {
      end = current;
    } else {
      ranges.push(start === end ? `${start}` : `${start}-${end}`);
      start = end = current;
    }
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);

  return ranges.join(",");
}

function parseRangeList(input:string): number[] {
  const numbers = new Set<number>();
  const parts = input.split(",");

  for (let part of parts) {
    part = part.trim();
    if (!part) continue;

    if (part.includes("-")) {
      const [startStr, endStr] = part.split("-").map(s => s.trim());
      const start = parseInt(startStr, 10);
      const end = parseInt(endStr, 10);

      if (!isNaN(start) && !isNaN(end)) {
        const [min, max] = start <= end ? [start, end] : [end, start]; 
        for (let i = min; i <= max; i++) {
          numbers.add(i);
        }
      }
    } else {
      const n = parseInt(part, 10);
      if (!isNaN(n)) numbers.add(n);
    }
  }

  return Array.from(numbers).sort((a, b) => a - b);
}


const handleCohortUpdate = (value:string) => {
    assayDetails.value!.numberOfParticipants = parseRangeList(value);
};


const getDatasets = async (workflowCategory:string) => {
    const datasets = await useDashboardGetDatasets(workflowCategory);
    return datasets;
};

const validate = async (): Promise<boolean> => {
    if (!formRef.value) return true;
    const { valid } = await formRef.value.validate();
    return valid;
};

defineExpose({ validate });

</script>

<style scoped>
.workflow-name{
    font-size: 1rem;
    font-weight: 500;
    color: #e9f2f5;
}
.assay-form-subtitle{
    font-size: 1rem;
    font-weight: 650;
}
/* Each section sits on the same subtle glass; a single accented left border
   keeps the four groups visually distinguishable without the old loud tints. */
.workflow, .input, .output, .cohort {
    width: 95%;
    padding: 12px 16px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(120, 200, 220, 0.12);
}
.workflow { border-left: 3px solid #5fd6e8; }
.input    { border-left: 3px solid #6fd49a; }
.output   { border-left: 3px solid #ffb74d; }
.cohort   { border-left: 3px solid #c792ea; }

.accent-workflow { color: #5fd6e8; }
.accent-input    { color: #6fd49a; }
.accent-output   { color: #ffb74d; }
.accent-cohort   { color: #c792ea; }
</style>