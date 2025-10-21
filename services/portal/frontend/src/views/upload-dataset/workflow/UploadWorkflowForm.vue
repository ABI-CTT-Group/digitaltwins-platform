<template>
    <v-container class="d-flex align-center justify-center">
        <v-card
            class="pa-6 responsive-box d-flex flex-column align-center justify-center"
            elevation="12"
            style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
        >
        <h2 class="w-100 text-center my-3">New Workflow</h2>
        <v-stepper v-model="step" alt-labels class="sheet-stepper" >
            <!-- Step Headers -->
            <v-stepper-header>
                <v-stepper-item
                    title="Registration"
                    :value= "1"
                    color="cyan-lighten-1"
                    :complete="step > 1"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Annotation"
                    :value="2"
                    color="cyan-lighten-1"
                    :complete="step > 2"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Build"
                    :value="3"
                    color="cyan-lighten-1"
                    :complete="step > 3"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Complete"
                    :value="4"
                    color="cyan-lighten-1"
                    :editable="false"
                    :complete="step > 4"
                ></v-stepper-item>
            </v-stepper-header>

            <!-- Step Contents -->
            <v-stepper-window>
                <v-stepper-window-item :value="1">
                    <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
                        <WorkflowInfomationStep @submit="handleSubmit" @cancel="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="2">
                    <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
                        <WorkflowAnnotateStep :workflow="workflow" @annotation-submit="handleAnnotation" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="3">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                        <WorkflowBuildStep :workflow="workflow" @build="handleBuild" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="4">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                        <WorkflowCompleteStep :workflow="workflow" @done="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>
            </v-stepper-window>
        </v-stepper>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import WorkflowInfomationStep from './components/WorkflowInfomationStep.vue';
import WorkflowAnnotateStep from './components/WorkflowAnnotateStep.vue';
import WorkflowCompleteStep from './components/WorkflowCompleteStep.vue';
import WorkflowBuildStep from './components/WorkflowBuildStep.vue';
import { IWorkflowInformationStep, IWrokflowResponse, IAnnotation} from '@/models/uiTypes';
import { useCreateWorkflow, useCreateWorkflowAnnotation, useWorkflowBuild } from '@/plugins/workflow_api'
import { ref, watch } from "vue";

const emit = defineEmits(['finished'])
const step = ref(0);
const  workflow = ref<IWrokflowResponse>()

const handleSubmit = async (data:IWorkflowInformationStep)=>{
    workflow.value  = await useCreateWorkflow(data)

    step.value += 1;
}

const handleAnnotation = async (id:string, annotation:IAnnotation)=>{
    const a = await useCreateWorkflowAnnotation(id, annotation)
    step.value += 1;
}

const handleBuild = async (id:string)=>{
    await useWorkflowBuild(id)
    step.value += 1;
}

const handleCancel = ()=>{
    emit('finished')
}
</script>

<style scoped>
.responsive-box {
  width: 90% !important;
}

@media (min-width: 2100px) {
  .responsive-box {
    width: 75% !important;
  }
}
.sheet-stepper{
    width: 95%;
    min-height: 50vh;
    background: rgba(1, 62, 62, 0.15); 
    /* border: 1px solid rgba(255, 255, 255, 0.125); */
    border-radius: 10px !important;
    box-shadow:  5px 5px 10px #071b25,
             -5px -5px 10px #0d3547 !important;
}

</style>