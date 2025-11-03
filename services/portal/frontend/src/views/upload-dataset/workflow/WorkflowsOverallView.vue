<template>
    <v-container class="d-flex align-center justify-center">
        <v-card
            class="pa-6 responsive-box d-flex flex-column align-center justify-center"
            elevation="12"
            style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
        >
        <div class="w-100 d-flex justify-start">
            <v-btn
                color="pink"
                :text="'Register a new workflow'"
                variant="tonal"
                :width="350"
                rounded="md"
                prepend-icon="mdi-plus-circle-outline"
                class="hover-animate my-2"
                @click="handleRegister"
            ></v-btn>
        </div>
        
        <div class="d-flex flex-column w-100 my-2 pa-5 border-sm rounded tool-conatiner">
            <Search 
                :label="'Search workflows'"
                v-model:search="search"
                @on:search="handleSearch" />
            <Refresh @on:refresh="handleRefresh"/>
            <div class="d-flex flex-grow-1">
                <div v-if="displayWorkflows.length > 0" class="d-flex flex-wrap ga-10 pa-5 justify-start">
                    <WorkflowCard
                        v-for="w in displayWorkflows"
                        :key="w.id" 
                        :workflow="w"
                        @delete="(id:string) => handleDeleteWorkflow(id)"
                        @submit-approve="(id:string) => handleWorkflowApproval(id)"
                    />
                </div>
                <NoData v-else />
            </div>
        </div>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import { ref, onBeforeMount, watch, onUnmounted } from "vue"
import WorkflowCard from "./components/WorkflowCard.vue"
import { useWorkflow, useDeleteWorkflow, useWorkflowApproval } from '@/plugins/workflow_api';
import { IWrokflowResponse } from '@/models/uiTypes';
import { useRouter } from 'vue-router'
import Fuse from "fuse.js";
import NoData from '@/views/upload-dataset/components/NoData.vue';
import Search from '@/views/upload-dataset/components/Search.vue';
import Refresh from "@/views/upload-dataset/components/Refresh.vue";

const router = useRouter();

const emit = defineEmits(["register"]);
const search = ref("");
const workflows = ref<Array<IWrokflowResponse>>([]);
const displayWorkflows = ref<Array<IWrokflowResponse>>([]);
const isAnyStatusPending = ref(false);
let refreshInterval: number | undefined;

onBeforeMount(async ()=>{
    await handleRefresh()
})

watch(search,(newVal, oldVal)=>{
    if(!newVal){
        displayWorkflows.value = workflows.value;
    }
})

watch(isAnyStatusPending, (newVal) => {
  if (newVal) {
    if (!refreshInterval) {
      console.log("start worklfow refresh");
      refreshInterval = window.setInterval(() => {
        handleRefresh().catch(err => console.error('refresh failed!', err));
      }, 5000);
    }
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = undefined;
      console.log("stop workflow refresh");
    }
  }
}, { immediate: true });


const handleRefresh = async () => {
    workflows.value = displayWorkflows.value = await useWorkflow();
    const anyBuilding = workflows.value.some(workflow => workflow.status === "building");
    isAnyStatusPending.value = anyBuilding;
}

const handleSearch = ()=>{
    if(!search.value){
        return
    }
    const fuse = new Fuse(workflows.value, {
        keys: ["name"],   
        threshold: 0.4    
    });
    displayWorkflows.value = fuse.search(search.value).map(r => r.item)
}
const handleRegister = ()=>{
    emit("register")
}


const handleDeleteWorkflow = async (id: string) =>{
    const res = await useDeleteWorkflow(id)
    if(!!res){
        await handleRefresh()
    }
}

const handleWorkflowApproval = async (id: string) => {
    // Call the API to submit the workflow for approval
    try {
        const res = await useWorkflowApproval(id);
        if (res) {
            alert('Workflow submitted for approval successfully.');
        } else {
            alert('Failed to submit workflow for approval.');
        }
    } catch (error) {
        console.error('Error submitting workflow for approval:', error);
        alert('An error occurred while submitting the workflow for approval.');
    }
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
.header {
    background: rgba(3, 252, 252, 0.05); 
    border-radius: 10px !important;
}
.subtitle {
  font-size: 14px;
  color: #666;
  white-space: nowrap;    
  overflow: hidden;        
  text-overflow: ellipsis;   
}
.v-list-item {
  min-height: 32px !important;  
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.tool-conatiner{
    min-height: 50vh;
}

</style>