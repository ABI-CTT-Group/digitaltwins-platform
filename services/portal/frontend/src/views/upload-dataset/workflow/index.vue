<template>
    <div class="container d-flex justify-center" style="padding-top: 16px;">
        <div class="w-100">
            <BackLink to="CatalogueDashboardView" label="Catalogue" sticky class="mb-4" />
            <Hero
                :title="heroDetail.title"
                :subtitle="heroDetail.subtitle"/>

            <WorkflowsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadWorkflowForm v-else @finished="handleUploadFinished"/>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/domain/Hero.vue';
import BackLink from '@/components/common/BackLink.vue';
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

</style>