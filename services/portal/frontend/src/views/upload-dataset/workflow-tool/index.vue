<template>
    <div class="container d-flex justify-center">
        <div class="w-100">
            <BackLink to="CatalogueDashboardView" label="Catalogue" class="mb-4" />
            <Hero
                :title="heroDetail.title"
                :subtitle="heroDetail.subtitle"/>

            <ToolsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadToolForm v-else @finished="handleUploadFinished"/>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/domain/Hero.vue';
import BackLink from '@/components/common/BackLink.vue';
import UploadToolForm from './UploadToolForm.vue';
import ToolsOverallView from './ToolsOverallView.vue';
import { ref, computed } from 'vue';
const showOverall = ref(true);
const heroDetail = computed(()=>{
    if(showOverall.value){
        return {
            title:'Workflow Tool Hub',
            subtitle:'Browse all tools — create, upload, and build Web GUI or CWL Script tools effortlessly, and preview results seamlessly.'
        }
    }else{
        return {
            title:'Upload & Configure Workflow Tool',
            subtitle:'From basic setup to build & preview — all in one simple interface.'
        }
    }
})
const handleUploadFinished = () => {
    showOverall.value = true;
}
</script>

<style scoped>
</style>