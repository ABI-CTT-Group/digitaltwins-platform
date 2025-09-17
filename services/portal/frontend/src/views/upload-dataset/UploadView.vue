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
                    value="1"
                    color="cyan-lighten-1"
                    :complete="step > 1"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Build & Test"
                    value="2"
                    color="cyan-lighten-1"
                    :complete="step > 2"
                    :editable="step > 1"
                ></v-stepper-item>
                <v-divider></v-divider>
                <v-stepper-item
                    title="Preview & Upload"
                    value="3"
                    color="cyan-lighten-1"
                    :editable="false"
                    :complete="step > 3"
                ></v-stepper-item>
            </v-stepper-header>

            <!-- Step Contents -->
            <v-stepper-window>
                <v-stepper-window-item value="1">
                    <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
                        <ToolInfomationStep @submit="handleSubmit" @cancel="handleCancel"/>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item value="2">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                    <p class="text-body-1">配置 Build 命令，例如 npm run build / docker build。</p>
                    </v-card>
                </v-stepper-window-item>

                <v-stepper-window-item value="3">
                    <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
                    <p class="text-body-1">设置 Prebuild 步骤，例如依赖安装、环境准备。</p>
                    </v-card>
                </v-stepper-window-item>
            </v-stepper-window>
        </v-stepper>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import ToolInfomationStep from './components/ToolInfomationStep.vue';
import { IToolInformationStep } from '@/models/uiTypes'
import { ref, watch } from "vue";

const emit = defineEmits(['finished'])
const step = ref(0);

const handleSubmit = (data:IToolInformationStep)=>{
    console.log(data);
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
    background: rgba(1, 62, 62, 0.15); 
    /* border: 1px solid rgba(255, 255, 255, 0.125); */
    border-radius: 10px !important;
    box-shadow:  5px 5px 10px #071b25,
             -5px -5px 10px #0d3547 !important;
}
</style>