<template>
    <v-container class="d-flex align-center justify-center">
        <v-card
            class="pa-6 responsive-box d-flex flex-column align-center justify-center"
            elevation="12"
            style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
        >
        <h2 class="w-100 text-center my-3">New Workflow Tool</h2>
        <v-stepper v-model="step" alt-labels editable class="sheet-stepper" >
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
                    :editable="step > 1"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Build & Test"
                    :value="3"
                    color="cyan-lighten-1"
                    :complete="step > 3"
                    :editable="step > 2"
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
                        <BaseInformationStep type="tool" @submit="handleSubmit" @cancel="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="2">
                    <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
                        <BaseAnnotateStep type="tool" :data="tool" :pending-auth="pendingAuth" @annotation-submit="handleAnnotation" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="3">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                        <BaseBuildStep type="tool" :data="tool" @build="handleBuild" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="4">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                        <BaseCompleteStep type="tool" :data="tool" @done="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>
            </v-stepper-window>
        </v-stepper>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import BaseInformationStep from '../components/BaseInformationStep.vue';
import BaseBuildStep from '../components/BaseBuildStep.vue';
import BaseCompleteStep from '../components/BaseCompleteStep.vue';
import BaseAnnotateStep from '../components/BaseAnnotateStep.vue';
import type { ToolResponse, BaseInformationStep as BaseInfoStepType, AnnotateTool, TransientAuth} from '@/models/types';
import { useCreateTool, useWorkflowToolBuild, useCreateToolAnnotation } from '@/bootstrap/tool_api'
import { ref, watch } from "vue";

const emit = defineEmits(['finished'])
const step = ref(0);
const tool = ref<ToolResponse>()
// Transient auth captured at registration step — used once for the FIRST
// build POST body, then discarded. Per phase-0.2 decision, we don't store
// it anywhere; rebuilds (later) prompt the user to re-enter it.
const pendingAuth = ref<TransientAuth | undefined>(undefined)

const handleSubmit = async (data: BaseInfoStepType, auth?: TransientAuth)=>{
    tool.value = await useCreateTool(data)
    pendingAuth.value = auth
    step.value += 1;
}

const handleAnnotation = async (id:string, data:AnnotateTool) =>{

    const res = await useCreateToolAnnotation(id, {
        fhirNote: JSON.stringify(data),
        sparcNote: ""
    })

    step.value += 1;
}

const handleBuild = async (id:string)=>{
    await useWorkflowToolBuild(id, pendingAuth.value)
    pendingAuth.value = undefined  // single-use; rebuild will re-prompt
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