<template>
    <div class="container d-flex justify-space-between align-center h-screen">
        <DashboardCard 
            :src="studyImage" 
            :title="'Study Dashboard'"
            location="Auckland Bioengineering Institute"
            description="The Study Dashboard enables researchers to edit assays, configure parameters, and launch workflows efficiently, ensuring accuracy, reproducibility, and streamlined research."
            @on-explore="handleExploreClicked"
            />
        <DashboardCard 
            :src="clinicalImage"
            :title="'Clinician Dashboard'"
            location="Auckland Bioengineering Institute"
            description="The Clinician Dashboard enables clinicians to view patient data, access clinical reports, and manage patient records efficiently, ensuring accuracy, reproducibility, and streamlined healthcare."
            @on-explore="handleExploreClicked"
            />
        
    </div>
</template>

<script setup lang="ts">
import DashboardCard from './components/DashboardCard.vue';
import clinicalImage from '@/assets/dashboard/clinical-01.jpg';
import studyImage from '@/assets/dashboard/study-01.jpg';
import { useRouter, useRoute } from 'vue-router';


const router = useRouter();

const handleExploreClicked = (title: string) => {
   
    if(title === 'Study Dashboard') {
        router.push({name:'StudyDashboard'});
    } else {
        console.log(`Explore clicked: ${title}`);
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