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
            <div class="d-flex justify-space-between w-100 header px-2 py-5">
                <v-text-field
                    v-model="search"
                    label="Search workflow tools"
                    variant="outlined"
                    prepend-inner-icon="mdi-magnify"
                    clearable
                    hide-details
                />
                <v-btn
                    :text="'search'"
                    variant="tonal"
                    :width="150"
                    rounded="md"
                    class="hover-animate ma-2"
                    @click="handleSearch"
                ></v-btn>
            </div>
            <div class="d-flex justify-end">
                <v-btn
                    color="blue"
                    :text="'refresh'"
                    variant="tonal"
                    :width="150"
                    rounded="md"
                    class="hover-animate ma-2"
                    @click="handleRefresh"
                ></v-btn>
            </div>
            <div class="d-flex flex-grow-1">
                <div v-if="displayTools.length > 0" class="d-flex flex-wrap ga-10 pa-5 justify-start">
                    <ToolCard
                        v-for="tool in displayTools"
                        :key="tool.id" 
                        :tool="tool"
                        @launch="(id:string) => handleLaunch(id)"
                        @rebuild="(id:string) => handleRebuild(id)"
                        @deploy="(id:string) => handleDeploy(id)"
                        @delete="(id:string) => handleDeleteTool(id)"
                        @submit-approve="(id:string) => handleToolApproval(id)"
                    />
                </div>
                <div v-else class="w-100 flex-grow-1 d-flex flex-column justify-center align-center">
                    <v-icon size="64" color="yellow-darken-1">mdi-database-off</v-icon>
                    <h2 class="mt-4">No data available</h2>
                    <p class="text-grey">
                        It seems there is nothing to display here. Try refreshing or check back later.
                    </p>
                </div>
                
            </div>
        </div>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import { ref, onBeforeMount, watch, onUnmounted } from "vue"
import ToolCard from "./components/ToolCard.vue"
import { useWorkflowTools, useMinIoWorkflowToolMetadata, useWorkflowToolBuild, useDeleteTool, useToolApproval, useDeployTool } from '@/plugins/plugin_api';
import { PluginResponse, PluginMinIOToolMetadata } from '@/models/uiTypes';
import { useRemoteAppStore } from '@/store/remoteStore'
import { useRouter } from 'vue-router'
import Fuse from "fuse.js";

const router = useRouter();
const remoteAppStore = useRemoteAppStore();
const isAnyToolBuilding = ref(false);
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

watch(isAnyToolBuilding, (newVal) => {
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
  isAnyToolBuilding.value = anyBuilding;
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
    
    if(deployRes.status) {
        alert('Tool deployed successfully.');
    } else {
        alert('Failed to deploy tool.');
    }
}

const handleDeleteTool = async (id: string) =>{
    const res = await useDeleteTool(id)
    if(!!res){
        await handleRefresh()
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
.shadow-card {
    background: rgba(255, 245, 200, 0.15); 
    border-radius: 10px !important;
    box-shadow: 
        0 0 10px rgba(255, 230, 150, 0.6),  
        0 0 10px rgba(255, 220, 120, 0.5),  
        inset 0 0 10px rgba(255, 235, 180, 0.3) !important; 
}
.tool-conatiner{
    min-height: 50vh;
}

</style>