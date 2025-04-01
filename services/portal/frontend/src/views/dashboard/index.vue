<template>
    <div class="container d-flex justify-space-around align-center h-screen px-10">
        <DashboardCard 
            :src="clinicalImage"
            :title="'Clinician Dashboard'"
            location="Te Whatu Ora AI Lab"
            description="Enables clinicians to run AI/digital twin driven workflows and generate clinical reports."
            @on-explore="handleExploreClicked"
            />
        <DashboardCard 
            :src="studyImage" 
            :title="'Study Dashboard'"
            location="Te Whatu Ora AI Lab"
            description="Enables clinicians to collaborate with researchers to assess efficacy of AI/digital twin driven workflows."
            @on-explore="handleExploreClicked"
            />
        <DashboardCard 
            :src="catelogueImage" 
            :title="'Catalogue'"
            location="Auckland Bioengineering Institute"
            description="Enables clinicians to see what AI/digital twin driven workflows and medical devices are available or being developed in research programmes."
            @on-explore="handleExploreClicked"
            />
        
    </div>
</template>

<script setup lang="ts">
import DashboardCard from './components/DashboardCard.vue';
import clinicalImage from '@/assets/dashboard/clinical-01.jpg';
import studyImage from '@/assets/dashboard/study.jpg';
import catelogueImage from '@/assets/dashboard/catalogue.jpg';
import { useRouter, useRoute } from 'vue-router';


const router = useRouter();

const handleExploreClicked = (title: string) => {
   
    if(title === 'Study Dashboard') {
        router.push({name:'StudyDashboard', params: { dashboardType: 'study' }});
    } else if(title === 'Clinician Dashboard') {
        router.push({name:'StudyDashboard', params: { dashboardType: 'clinician' }});
    }else if(title === 'Catalogue') {
        window.open("http://130.216.217.147:3000/", '_blank');
    } else {
        console.log(`Unknown title: ${title}`);
    }
}
</script>

<style scoped>
.container {
    position: relative;
    background-image: url("@/assets/login_bg.jpg"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    backdrop-filter: blur(5px); 
    -webkit-backdrop-filter: blur(5px); 
}
.container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: inherit; 
  filter: blur(4px); 
  -webkit-filter: blur(4px); 
  z-index: -1; 
}
</style>