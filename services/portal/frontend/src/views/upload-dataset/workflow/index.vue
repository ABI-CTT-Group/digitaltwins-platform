<template>
    <HubShell :title="heroDetail.title" :subtitle="heroDetail.subtitle" accent="var(--accent-workflows)">

            <WorkflowsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadWorkflowForm v-else @finished="handleUploadFinished"/>
    </HubShell>
</template>

<script setup lang="ts">
import HubShell from '../components/HubShell.vue';
import UploadWorkflowForm from './UploadWorkflowForm.vue';
import WorkflowsOverallView from './WorkflowsOverallView.vue';
import { ref, computed } from 'vue';
const showOverall = ref(true);
const heroDetail = computed(()=>{
    if(showOverall.value){
        return {
            title:'Workflows',
            subtitle:'Register workflows that chain tools into the steps an assay runs.'
        }
    }else{
        return {
            title:'Register a workflow',
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