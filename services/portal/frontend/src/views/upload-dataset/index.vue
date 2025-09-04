<template>
    <div class="container overflow-hidden d-flex justify-center">
        <div class="overflow-y-auto sub-container">
            <Hero 
                :title="'Upload & Configure Workflow Tool'"
                :subtitle="'From basic setup to build & preview — all in one simple interface.'"/>

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
                                <ToolInfomationStep @submit="handleSubmit"/>
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

                    <!-- Footer Buttons -->
                    <!-- <v-stepper-actions class="d-flex justify-end mt-4">
                        <template #prev>
                            <v-btn
                                variant="outlined"
                                color="cyan-lighten-2"
                                :disabled="step === 1"
                                @click="step--"
                            >
                                Previous
                            </v-btn>
                        </template>

                        <template #next>
                            <div class="mx-3">
                                <v-btn
                                    v-if="step < steps.length"
                                    color="cyan-lighten-1"
                                    variant="flat"
                                    @click="step++"
                                >
                                    Next
                                </v-btn>
                                <v-btn
                                    v-else
                                    color="cyan-accent-3"
                                    variant="flat"
                                    @click="submit"
                                    :disabled="false"
                                >
                                    Submit
                                </v-btn>
                            </div>
                            
                        </template>
                    </v-stepper-actions> -->
                </v-stepper>
                </v-card>
            </v-container>
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/dt-components/Hero.vue';
import ToolInfomationStep from './components/ToolInfomationStep.vue';
import { IToolInformationStep } from '@/models/uiTypes'
import { ref, watch } from "vue";

const step = ref(0);

const handleSubmit = (data:IToolInformationStep)=>{
    console.log(data);
    step.value += 1;
}
</script>

<style scoped>
.sub-container{
    width: 100%;
    margin-top: 70px;
}
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