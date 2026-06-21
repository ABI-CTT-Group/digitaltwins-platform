<template>
    <div class="container d-flex justify-center" style="padding-top: 16px;">
        <div class="w-100">
            <BackLink to="CatalogueDashboardView" label="Catalogue" sticky class="mb-4" />
            <Hero
                :title="heroDetail.title"
                :subtitle="heroDetail.subtitle"/>

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
                :initial-status="logConsole.initialStatus.value"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
import Hero from '@/components/domain/Hero.vue';
import BackLink from '@/components/common/BackLink.vue';
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