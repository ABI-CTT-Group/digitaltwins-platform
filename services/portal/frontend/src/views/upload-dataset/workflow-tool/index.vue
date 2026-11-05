<template>
    <HubShell :title="heroDetail.title" :subtitle="heroDetail.subtitle" accent="var(--accent-tools)">

            <ToolsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadToolForm v-else @finished="handleUploadFinished"/>

            <!-- Single app-level log console, shared by the hub (rebuild/deploy/
                 view-logs) and the registration wizard (first build) via the
                 useLogConsole singleton. Mounted here so it survives the
                 hub <-> wizard v-if/v-else swap. -->
            <LogConsole
                v-model="logConsole.open.value"
                :kind="logConsole.kind.value"
                :job-id="logConsole.jobId.value"
                :title="logConsole.title.value"
                :started-at="logConsole.startedAt.value"
                :ended-at="logConsole.endedAt.value"
                :initial-status="logConsole.initialStatus.value"
            />
    </HubShell>
</template>

<script setup lang="ts">
import HubShell from '../components/HubShell.vue';
import UploadToolForm from './UploadToolForm.vue';
import ToolsOverallView from './ToolsOverallView.vue';
import LogConsole from '../components/LogConsole.vue';
import { useLogConsole } from '@/composables/useLogConsole';
import { ref, computed } from 'vue';
const logConsole = useLogConsole();
const showOverall = ref(true);
const heroDetail = computed(()=>{
    if(showOverall.value){
        return {
            title:'Tools',
            subtitle:'Register and build the tools that workflows and assays run.'
        }
    }else{
        return {
            title:'Register a tool',
            subtitle:'Add its source and details, annotate it for FHIR, then build it.'
        }
    }
})
const handleUploadFinished = () => {
    showOverall.value = true;
}
</script>

<style scoped>
</style>