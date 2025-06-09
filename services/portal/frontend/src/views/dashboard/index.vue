<template>
    <div class="container overflow-hidden d-flex justify-center">
        <NavHome />
        <div class="overflow-y-auto h-100 mt-10 sub-container">
            <v-row>
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                >
                    <DashboardCard 
                        :src="tutorialImage" 
                        :title="'How It Works'"
                        location="Auckland Bioengineering Institute"
                        description="Helps clinicians quickly learn how to use the app with a simple, guided overview designed to make getting started easy."
                        @on-explore="handleExploreClicked"
                        />    
                    <DashboardCard 
                        :src="clinicalImage"
                        :title="'Clinician Dashboard'"
                        location="Te Whatu Ora AI Lab"
                        description="Enables clinicians to run AI/digital twin driven workflows and generate clinical reports."
                        @on-explore="handleExploreClicked"
                        />
                </v-col> 
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                >
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
                </v-col>
            </v-row>
        </div>
        
    </div>
</template>

<script setup lang="ts">
import DashboardCard from './components/DashboardCard.vue';
import clinicalImage from '@/assets/dashboard/clinical-01.jpg';
import studyImage from '@/assets/dashboard/study.jpg';
import catelogueImage from '@/assets/dashboard/catalogue.jpg';
import tutorialImage from '@/assets/dashboard/study-01.jpg';
import NavHome from './components/NavHome.vue';
import { useRouter, useRoute } from 'vue-router';


const router = useRouter();

const handleExploreClicked = (title: string) => {
   
    if(title === 'Study Dashboard') {
        router.push({name:'Dashboard', params: { dashboardType: 'study' }});
    } else if(title === 'Clinician Dashboard') {
        router.push({name:'Dashboard', params: { dashboardType: 'clinician' }});
    }else if(title === 'Catalogue') {
        router.push({name:"CatalogueDashboardView"})
    }else if(title === "How It Works"){
        router.push({name:'TutorialDashboard'});
    }else {
        console.log(`Unknown title: ${title}`);
    }
}
</script>

<style scoped>
.container {
    height: 100vh;
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
  filter: blur(2px); 
  -webkit-filter: blur(2px); 
  z-index: -1; 
}
.sub-container{
    width: 80%;
}

</style>