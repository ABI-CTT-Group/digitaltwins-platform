<template>
    <div class="container overflow-hidden d-flex justify-center">
        <div class="overflow-y-auto sub-container">
            <Hero 
                :title="heroDetail.title"
                :subtitle="heroDetail.subtitle"/>

            <ToolsOverallView v-if="showOverall" @register="showOverall=false"/>
            <UploadView v-else @finished="handleUploadFinished"/>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/dt-components/Hero.vue';
import UploadView from './UploadView.vue';
import ToolsOverallView from './ToolsOverallView.vue';
import { ref, computed } from 'vue';
const showOverall = ref(true);
const heroDetail = computed(()=>{
    if(showOverall.value){
        return {
            title:'Workflow Tool Hub',
            subtitle:'Browse all tools, create and upload new ones, build with ease, and preview results seamlessly.'
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
.sub-container{
    width: 100%;
    margin-top: 70px;
}

</style>