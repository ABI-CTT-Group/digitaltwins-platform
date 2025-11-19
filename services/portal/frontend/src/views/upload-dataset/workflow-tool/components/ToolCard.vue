
<template>
  <!-- rgba(15, 25, 35, 0.15) -->
    <CardUI 
      card-style="background: rgba(75, 204, 255, 0.03);"
      :is-deleting="isDeleting"
      v-model:menu="menu"
    >
      <template #launch>
        <v-btn
            v-if="isBuilding"
            color="deep-purple"
            variant="flat" 
            size="small"
            class="text-white mx-2" 
            rounded="md" 
            disabled
        >   
            <v-progress-circular
                indeterminate
                size="15"
                width="2"
                color="white"
                class="mr-2"
            />
            Building
        </v-btn>
        <v-btn
            v-else-if="isDeploying"
            color="deep-purple"
            variant="flat" 
            size="small"
            class="text-white mx-2" 
            rounded="md" 
            disabled
        >   
            <v-progress-circular
                indeterminate
                size="15"
                width="2"
                color="white"
                class="mr-2"
            />
            Deploying
        </v-btn>
        <v-btn 
            v-else
            color="deep-purple" 
            variant="flat" 
            size="small" 
            class="text-white mx-2" 
            rounded="md" 
            :disabled="(tool.status != 'completed') ? true : false"
            @click.stop="onLaunch">
            Launch
        </v-btn>
      </template>
      <template #menu>
        <v-list density="compact" class="py-0 cursor-pointer">
            <v-list-item density="compact" @click.stop="onRebuild">
                <v-list-item-title class="hover-animate px-2">Rebuild Tool</v-list-item-title>
            </v-list-item>
            <v-list-item density="compact" @click.stop="onSubmit">
                <v-list-item-title class="hover-animate px-2">Submit to Approval</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="tool.has_backend && tool.label=='GUI'" density="compact" @click.stop="onDeploy">
                <v-list-item-title class="hover-animate px-2">Deploy Backend</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="tool.deploy_status == 'completed' && tool.label=='GUI'" density="compact" @click.stop="onDockerComposeUp">
                <v-list-item-title class="hover-animate px-2">Compose Up</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="tool.deploy_status == 'completed' && tool.label=='GUI'" density="compact" @click.stop="onDockerComposeDown">
                <v-list-item-title class="hover-animate px-2">Compose Down</v-list-item-title>
            </v-list-item>
            <v-list-item density="compact" @click.stop="onDelete" color="red">
                <v-list-item-title class="text-red hover-animate px-2">Delete Tool</v-list-item-title>
            </v-list-item>
        </v-list>
      </template>
      <template #name>
        <v-tooltip :text="tool.name" location="top"  max-width="300">
          <template #activator="{ props }">
            <p v-bind="props" class="text-truncate" style="max-width:400px;">
              {{ tool.name }}
            </p>
          </template>
        </v-tooltip>
      </template>
      <template #description>{{ tool.description }}</template>
      <template #tags>
        <v-chip v-if="!!tool.version" size="small" color="blue-lighten-4" text-color="blue-darken-3" class="mx-1 my-1">v{{ tool.version }}</v-chip>
        <v-chip v-if="!!tool.author" size="small" color="blue-lighten-5" text-color="blue-darken-3" class="mx-1 my-1">{{ tool.author }}</v-chip>
        <v-chip v-if="!!tool.author" size="small" color="orange-lighten-2" text-color="green-darken-3" class="mx-1 my-1">{{ tool.label }}</v-chip>
        <v-chip v-if="!!tool.status" size="small" :color="statusColor" :text-color="statusTextColor" class="mx-1 mr-1 my-1">pre build: {{ tool.status }}</v-chip>
        <v-chip v-if="!!tool.deploy_status" size="small" :color="deployStatusColor" :text-color="deployStatusTextColor" class="mx-1 mr-1 my-1">deploy: {{ tool.deploy_status }}</v-chip>
      </template>
      <template #time>
        <v-chip v-if="!!tool.created_at" size="small" color="green-lighten-4" text-color="green-darken-2" class="ms-auto">{{ formatDate(tool.created_at) }}</v-chip>
      </template>
    </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, watch, toRef } from 'vue'
import { PluginResponse } from '@/models/uiTypes';
import { useGetDockerComposeStatus, useDeleteTool } from '@/plugins/plugin_api'
import CardUI from '../../components/CardUI.vue';
import { formatDate } from '../../components/utils';

const props = defineProps<{
  tool: PluginResponse
}>()

const menu = ref(false);
const tool = toRef(props, "tool")
const isDeleting = ref(false)

const isBuilding = computed(()=>{
    return tool.value.status == "building" ? true : false;
})
const isDeploying = computed(()=>{
    if(!tool.value.has_backend ) return false;
    if(!tool.value.deploy_status) return false;
    return tool.value.deploy_status == "deploying" ? true : false;
})

const statusColor = computed(() => {
  switch (props.tool.status) {
    case "pending":
      return "amber-lighten-2"
    case "building":
      return "blue-lighten-2"
    case "failed":
      return "red-lighten-2"
    case "completed":
      return "green-lighten-2"
    default:
      return ""
  }
})

const statusTextColor = computed(() => {
  switch (props.tool.status) {
    case "pending":
      return "amber-darken-3"
    case "building":
      return "blue-darken-3"
    case "failed":
      return "red-darken-3"
    case "completed":
      return "green-darken-3"
    default:
      return ""
  }
})

const deployStatusColor = computed(() => {
  switch (props.tool.deploy_status) {
    case "pending":
      return "amber-lighten-2"
    case "deploying":
      return "blue-lighten-2"
    case "failed":
      return "red-lighten-2"
    case "completed":
      return "green-lighten-2"
    default:
      return ""
  }
})

const deployStatusTextColor = computed(() => {
  switch (props.tool.deploy_status) {
    case "pending":
      return "amber-darken-3"
    case "deploying":
      return "blue-darken-3"
    case "failed":
      return "red-darken-3"
    case "completed":
      return "green-darken-3"
    default:
      return ""
  }
})


const emit = defineEmits(["launch", "rebuild", "submit-approve", "deploy", "compose-up", "compose-down", "delete"])

const onLaunch = async () => {
    if(tool.value.label === "Script"){
        alert("CWL Script tool cannot be launched. Please download the script and run it locally.");
        return;
    }
    if (tool.value.has_backend && !tool.value.latest_deploy_id && tool.value.deploy_status !== 'completed') {
        alert("Tool backend is not deployed yet. Please deploy the backend first.");
        return;
    }else if(!!tool.value.latest_deploy_id && !await useGetDockerComposeStatus(tool.value.latest_deploy_id).catch(() => false)){
        alert("Tool backend is not running. Please start the backend by 'Compose Up' first.");
        return;
    }
    emit("launch", tool.value.id)
}
const onRebuild = () => {
    menu.value = false;
    tool.value.status = "building"
    emit("rebuild", tool.value.id)
}
const onSubmit = () => {
    menu.value = false;
    emit("submit-approve", tool.value.id)
}
const onDeploy = () => {
    menu.value = false;
    emit("deploy", tool.value.id)
}
const onDockerComposeUp = () => {
    menu.value = false;
    emit("compose-up", tool.value.latest_deploy_id)
}
const onDockerComposeDown = () => {
    menu.value = false;
    emit("compose-down", tool.value.latest_deploy_id)
}
const onDelete = async () => {
    menu.value = false;
    isDeleting.value = true;
    const res:any = await useDeleteTool(tool.value.id)
    
    if(!res["status"]){
      isDeleting.value = false;
      alert("Error: " + res["message"])
    }
    emit("delete", res)
}
</script>

<style scoped>
.title {
    font-size: large;
}

.subtitle{
    font-size: small;
    line-height: 1.5em;         
    max-height: 4em;             
    overflow: hidden;
    display: -webkit-box;
    box-orient: vertical;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;        
    text-overflow: ellipsis; 
}
.card-hover-animate {
  transition: all 0.3s ease;
  transform: scale(1);
}
.card-hover-animate:hover {
  transform: scale(1.02) !important;
  box-shadow:
        0 0 15px rgba(75, 204, 255, 0.6),
        0 0 25px rgba(75, 204, 255, 0.4),
        inset 0 0 10px rgba(75, 204, 255, 0.25) !important;
}

.shadow-card {
  background: rgba(75, 204, 255, 0.1);
  border-radius: 10px !important;
  border: 1px solid rgba(255, 255, 255, 0.12);
  
}

</style>