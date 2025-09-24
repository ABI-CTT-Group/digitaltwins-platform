<template>

    <div class="back-arrow">
       <v-btn 
          icon="mdi-arrow-left" 
          variant="tonal"
          class="hover-animate"
          @click="$router.back()"
          ></v-btn>
    </div>
    <div class="container d-flex justify-center">
        <div class="overflow-y-auto sub-container d-flex flex-column align-center no-select">
            <v-container fluid class="py-10">
                <v-row justify="center">
                    <v-col cols="12" md="10">
                        <div class="plugin-title">
                          <h1>Launched Assay Overview</h1>
                          <p class="subtitle">Integrate your clinical tools, workflows, and datasets seamlessly</p>
                        </div>

                        <v-card class="pa-6 mb-10 " elevation="4">
                          <h2 class="pipeline-title font-weight-medium mb-4">Workflow Overview</h2>
                          <v-row>
                              <v-col cols="12" md="6">
                                <p><strong>Name:</strong> {{ workflow.name }}</p>
                                <p><strong>Version:</strong> {{ workflow.version }}</p>
                                <p><strong>Created By:</strong> {{ workflow.author }}</p>
                              </v-col>
                              <v-col cols="12" md="6">
                                <p><strong>license:</strong> {{ workflow.license }}</p>
                                <p><strong>Total Tools:</strong> {{ workflow.tools.length }}</p>
                              </v-col>
                          </v-row>
                        </v-card>

                        <v-card class="pa-6 mb-10" elevation="4">
                          <h2 class="pipeline-title font-weight-medium mb-4">Workflow Tools</h2>
                          <v-row dense>
                              <v-col
                                v-for="tool in workflow.tools"
                                :key="tool.id"
                                cols="12"
                                md="6"
                              >
                                <v-card class="mb-4 tool-card" variant="tonal" >
                                    <v-card-title class="text-h6">{{ tool.name }}</v-card-title>
                                    <v-card-text>
                                    <p><strong>Type:</strong> {{ tool.type }}</p>
                                    <p><strong>Image:</strong> {{ tool.image }}</p>
                                    <p><strong>Command:</strong> {{ tool.command }}</p>
                                    <p><strong>Description:</strong> {{ tool.description }}</p>
                                    </v-card-text>
                                </v-card>
                              </v-col>
                          </v-row>
                        </v-card>

                        <v-card class="pa-6" elevation="4">
                          <h2 class="pipeline-title font-weight-medium mb-4">Linked Datasets</h2>
                          <v-list lines="two">
                              <v-list-item
                              v-for="dataset in workflow.datasets"
                              :key="dataset.id"
                              class="mb-2"
                              >
                                  <template v-slot:prepend>
                                    <v-icon icon="mdi-database-outline" />
                                  </template>
                                  <v-list-item-title>{{ dataset.name }}</v-list-item-title>
                                  <v-list-item-subtitle>{{ dataset.description }}</v-list-item-subtitle>
                              </v-list-item>
                          </v-list>
                        </v-card>
                    </v-col>
                </v-row>
            </v-container>
        </div>
    </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { asyncComputed } from '@vueuse/core'
import { ref, computed, onMounted, onBeforeMount, watchEffect} from 'vue';
import { useDashboardPageStore } from '@/store/states';
import { useDashboardWorkflowDetail } from "@/plugins/dashboard_api";

import { storeToRefs } from "pinia";

const route = useRoute();

const { allAssayDetailsOfStudy } = storeToRefs(useDashboardPageStore());
onBeforeMount(async ()=>{
    // await getDashboardWorkflows();
}) 
onMounted(() => {
  
});

const workflow =  asyncComputed(async () => {
    const assayId = route.query.assayId as string;
    console.log(allAssayDetailsOfStudy.value);
    
    const assayDetails = allAssayDetailsOfStudy.value[assayId];
    console.log("assayDetails: ", assayDetails);
    
    const workflowId = assayDetails?.workflow?.seekId;
    const workflowFromSeek = await useDashboardWorkflowDetail(workflowId as string);
    console.log("workflowFromSeek: ", workflowFromSeek);
    
    return {
      name: workflowFromSeek.origin?.attributes.title,
      uuid: "",
      author: 'Dr. Jane Smith',
      version: '1.2.0',
      license: workflowFromSeek.origin?.attributes.license,
      tools: [
        {
          id: 1,
          name: 'FastQC',
          type: 'Quality Control',
          image: 'biocontainers/fastqc:v0.11.9_cv8',
          command: 'fastqc input.fq',
          description: 'Performs quality checks on raw sequence data.'
        },
        {
          id: 2,
          name: 'BWA',
          type: 'Alignment',
          image: 'biocontainers/bwa:v0.7.17_cv1',
          command: 'bwa mem ref.fa input.fq > aligned.sam',
          description: 'Aligns sequencing reads to a reference genome.'
        },
        {
          id: 3,
          name: 'GATK HaplotypeCaller',
          type: 'Variant Calling',
          image: 'broadinstitute/gatk:4.1.8.1',
          command: 'gatk HaplotypeCaller -I input.bam -O output.vcf',
          description: 'Calls genetic variants from aligned sequence data.'
        }
      ],
      datasets: [
        {
          id: 'd1',
          name: 'Human Genome Reference (GRCh38)',
          description: 'The full reference genome used for alignment and variant calling.'
        },
        {
          id: 'd2',
          name: 'Sample Sequencing Reads',
          description: 'Raw FASTQ reads from whole genome sequencing samples.'
        }
      ]
    }
  }, {
    name: '',
    uuid:'',
    author: '',
    version: '',
    license: '',
    tools: [],
    datasets: []
  });


</script>

<style scoped>

.sub-container{
    width: 90%;
    margin-top: 70px ;
    padding: 20px;
}

.plugin-title {
  text-align: center;
  margin-bottom: 60px;
}

.plugin-title h1 {
  font-size: 3.2rem;
  font-weight: 800;
  background: linear-gradient(90deg, #00bcd4, #29b6f6);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 12px rgba(0, 188, 212, 0.4);
  margin-bottom: 10px;
}

.plugin-title .subtitle {
  font-size: 1.125rem;
  color: #90a4ae;
  letter-spacing: 0.5px;
  margin-top: 8px;
}

.v-card {
  background-color: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  color: #cfd8dc;
  box-shadow: 0 4px 24px rgba(0, 188, 212, 0.08);
}

.v-card-title {
  color: #29b6f6;
  font-weight: 600;
}

h1, h2 {
  color: #ffffff;
}

.v-icon {
  color: #00bcd4;
}

.v-list-item-title {
  font-weight: 500;
  color: #e0f7fa;
}

.v-list-item-subtitle {
  color: #90a4ae;
}
.v-list{
  background-color:  rgba(0, 0, 0, 0.3) !important;
  border-radius: 12px;
}

.tool-card {
  background-color: rgba(0, 0, 0, 0.6) !important;
}

.back-arrow {
  position: fixed;
  top: 80px;
  left: 20px;
  z-index: 100;
}

.pipeline-title {
  font-weight: 600;
}
.no-select{
  user-select: none;
}

</style>