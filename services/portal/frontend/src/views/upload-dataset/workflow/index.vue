<template>
    <div class="container overflow-hidden d-flex justify-center">
        <div class="overflow-y-auto sub-container">
            <Hero 
                :title="heroDetail.title"
                :subtitle="heroDetail.subtitle"/>

            <WorkflowsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadWorkflowForm v-else @finished="handleUploadFinished"/>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/dt-components/Hero.vue';
import UploadWorkflowForm from './UploadWorkflowForm.vue';
import WorkflowsOverallView from './WorkflowsOverallView.vue';
import { ref, computed } from 'vue';
const showOverall = ref(true);
const heroDetail = computed(()=>{
    if(showOverall.value){
        return {
            title:'Workflow Hub',
            subtitle:'Explore all tools, design workflows effortlessly using Web GUI or CWL Script components.'
        }
    }else{
        return {
            title:'Upload & Annotate Workflow',
            subtitle:'Streamline your workflow creation and annotation in one intuitive interface.'
        }
    }
})
const handleUploadFinished = () => {
    showOverall.value = true;
}
</script>

<style scoped>
.sub-container{
    width: 100%;
    margin-top: 70px;
}

</style>