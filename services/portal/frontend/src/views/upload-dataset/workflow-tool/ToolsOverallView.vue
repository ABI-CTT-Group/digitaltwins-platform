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
                :text="'Register a new workflow tool'"
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
                :label="'Search workflow tools'"
                v-model:search="search"
                @on:search="handleSearch" />
            <Refresh @on:refresh="handleRefresh"/>
            <div class="d-flex flex-grow-1">
                <div v-if="displayTools.length > 0" class="d-flex flex-wrap ga-10 pa-5 justify-start">
                    <ToolCard
                        v-for="tool in displayTools"
                        :key="tool.id" 
                        :tool="tool"
                        @launch="(id:string) => handleLaunch(id)"
                        @rebuild="(id:string) => handleRebuild(id)"
                        @deploy="(id:string) => handleDeploy(id)"
                        @compose-up="(id:string) => handleExecuteDockerCompose(id, 'up')"
                        @compose-down="(id:string) => handleExecuteDockerCompose(id, 'down')"
                        @delete="(id:string) => handleDeleteTool(id)"
                        @submit-approve="(id:string) => handleToolApproval(id)"
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
import ToolCard from "./components/ToolCard.vue"
import { useWorkflowTools, useMinIoWorkflowToolMetadata, useWorkflowToolBuild, useDeleteTool, useToolApproval, useDeployTool, useDockerCompose } from '@/plugins/plugin_api';
import { PluginResponse, PluginMinIOToolMetadata } from '@/models/uiTypes';
import { useRemoteAppStore } from '@/store/remoteStore'
import { useRouter } from 'vue-router'
import Fuse from "fuse.js";
import NoData from '../components/NoData.vue';
import Search from '../components/Search.vue';
import Refresh from "../components/Refresh.vue";

const router = useRouter();
const remoteAppStore = useRemoteAppStore();
const isAnyToolStatusPending = ref(false);
let refreshInterval: number | undefined;

const emit = defineEmits(["register"]);
const search = ref("");
const workflowTools = ref<Array<PluginResponse>>([]);
const displayTools = ref<Array<PluginResponse>>([]);

onBeforeMount(async ()=>{
    await handleRefresh()
})

watch(search,(newVal, oldVal)=>{
    if(!newVal){
        displayTools.value = workflowTools.value;
    }
})

watch(isAnyToolStatusPending, (newVal) => {
  if (newVal) {
    if (!refreshInterval) {
      console.log("start refresh");
      refreshInterval = window.setInterval(() => {
        handleRefresh().catch(err => console.error('refresh failed!', err));
      }, 5000);
    }
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = undefined;
      console.log("stop refresh");
    }
  }
}, { immediate: true });

const handleRefresh = async () => {
  workflowTools.value = displayTools.value = await useWorkflowTools();

  const anyBuilding = workflowTools.value.some(tool => tool.status === "building");

  const anyDeploying = workflowTools.value.some(tool => tool.deploy_status === "deploying");

  isAnyToolStatusPending.value = anyBuilding || anyDeploying;
}

const handleSearch = ()=>{
    if(!search.value){
        return
    }
    const fuse = new Fuse(workflowTools.value, {
        keys: ["name"],   
        threshold: 0.4    
    });
    displayTools.value = fuse.search(search.value).map(r => r.item)
}
const handleRegister = ()=>{
    emit("register")
}
const handleLaunch = async (id:string) => {
    const metadata = await useMinIoWorkflowToolMetadata();
    if (!!metadata && metadata.components.length >0){
        const toolMetadata = metadata.components.find((tool:PluginMinIOToolMetadata)=>tool.id == id)
        if(!!toolMetadata){
            remoteAppStore.setRemoteApp({
                path: toolMetadata.path,
                expose: toolMetadata.expose,
                name: toolMetadata.name,
                description: toolMetadata.description
            })
            router.push({
                name: 'ToolPluginView'
            })
        }
    }
    console.warn(`Launch tool ${id} failed, cannot find the metadata in MinIO. `)
}
const handleRebuild = async (id:string) =>{
    const buildRes = await useWorkflowToolBuild(id);
    if(buildRes.status="building") await handleRefresh();
}

const handleDeploy = async (id:string) =>{
    // Implement deploy logic here
    console.log(`Deploy tool with id: ${id}`);
    // For example, you might call an API endpoint to deploy the tool
    const deployRes = await useDeployTool(id) as any;
    console.log(deployRes);
    if(deployRes.status="deploying") await handleRefresh();
}

const handleDeleteTool = async (res: any) =>{
    if(!!res){
        await handleRefresh()
    }
}

const handleExecuteDockerCompose = async (id: string, command: "up" | "down") => {
    try {
        const res = await useDockerCompose(id, command);
        console.log(res);
        
    } catch (error) {
        console.error(`Error executing Docker Compose ${command}:`, error);
        alert(`An error occurred while executing Docker Compose ${command}.`);
    }
}

const handleToolApproval = async (id: string) => {
    // Call the API to submit the tool for approval
    try {
        const res = await useToolApproval(id);
        if (res) {
            alert('Tool submitted for approval successfully.');
        } else {
            alert('Failed to submit tool for approval.');
        }
    } catch (error) {
        console.error('Error submitting tool for approval:', error);
        alert('An error occurred while submitting the tool for approval.');
    }
}

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
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