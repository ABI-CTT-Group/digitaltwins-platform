<template>
    <v-container class="d-flex align-center justify-center">
        <v-card
            class="pa-6 responsive-box d-flex flex-column align-center justify-center aurora-panel"
            flat
        >
        <h2 class="w-100 text-center my-3 wizard-title">New Workflow</h2>
        <v-stepper v-model="step" alt-labels class="sheet-stepper" >
            <!-- Step Headers -->
            <v-stepper-header>
                <v-stepper-item
                    title="Registration"
                    :value= "1"
                    color="#5fd6e8"
                    :complete="step > 1"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Annotation"
                    :value="2"
                    color="#5fd6e8"
                    :complete="step > 2"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Build"
                    :value="3"
                    color="#5fd6e8"
                    :complete="step > 3"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Complete"
                    :value="4"
                    color="#5fd6e8"
                    :editable="false"
                    :complete="step > 4"
                ></v-stepper-item>
            </v-stepper-header>

            <!-- Step Contents -->
            <v-stepper-window>
                <v-stepper-window-item :value="1">
                    <v-card class="pa-4 step-pane" flat>
                        <BaseInformationStep type="workflow" @submit="handleSubmit" @cancel="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="2">
                    <v-card class="pa-4 step-pane" flat>
                        <BaseAnnotateStep type="workflow" :data="workflow" :pending-auth="pendingAuth" @annotation-submit="handleAnnotation" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="3">
                    <v-card class="pa-4 step-pane" flat>
                        <BaseBuildStep type="workflow" :data="workflow" @build="handleBuild" @close="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item :value="4">
                    <v-card class="pa-4 step-pane" flat>
                        <BaseCompleteStep type="workflow" :data="workflow" @done="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>
            </v-stepper-window>
        </v-stepper>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import BaseInformationStep from '../components/BaseInformationStep.vue';
import BaseAnnotateStep from '../components/BaseAnnotateStep.vue';
import BaseCompleteStep from '../components/BaseCompleteStep.vue';
import BaseBuildStep from '../components/BaseBuildStep.vue';
import type { BaseInformationStep as BaseInfoStepType, WorkflowResponse, IAnnotation, TransientAuth} from '@/models/types';
import { useCreateWorkflow, useCreateWorkflowAnnotation, useWorkflowBuild } from '@/bootstrap/workflow_api'
import { ref, watch } from "vue";

const emit = defineEmits(['finished'])
const step = ref(0);
const  workflow = ref<WorkflowResponse>()
// Captured at registration, used once for first build (see UploadToolForm).
const pendingAuth = ref<TransientAuth | undefined>(undefined)

const handleSubmit = async (data: BaseInfoStepType, auth?: TransientAuth)=>{
    workflow.value  = await useCreateWorkflow(data)
    pendingAuth.value = auth
    step.value += 1;
}

const handleAnnotation = async (id:string, annotation:IAnnotation)=>{
    await useCreateWorkflowAnnotation(id, annotation)
    step.value += 1;
}

const handleBuild = async (id:string)=>{
    await useWorkflowBuild(id, pendingAuth.value)
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
.aurora-panel {
  background: rgba(8, 18, 26, 0.55) !important;
  border: 1px solid rgba(120, 200, 220, 0.16);
  border-radius: 20px !important;
}
.wizard-title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  color: #fff;
}
.sheet-stepper {
  width: 95%;
  min-height: 50vh;
  background: transparent !important;
  box-shadow: none !important;
}
.step-pane {
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid rgba(120, 200, 220, 0.14);
  border-radius: 14px !important;
}
</style>