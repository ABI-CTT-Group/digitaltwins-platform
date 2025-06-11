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
                        :title="'How to use this Platform'"
                        location="Auckland Bioengineering Institute"
                        description="Provides help and tutorials describing how to use the platform."
                        @on-explore="handleExploreClicked"
                        />    
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
                </v-col> 
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                > 
                    <DashboardCard 
                        :src="catelogueImage" 
                        :title="'Catalogue'"
                        location="Auckland Bioengineering Institute"
                        description="Enables clinicians to see what AI/digital twin driven workflows and medical devices are available or being developed in research programmes."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="fcMapImage" 
                        :title="'Physiology Exploration (FC Map)'"
                        location="SPARC"
                        description="Use the FC Map to explore physics informed biomedical models."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="mydigitaltwinImage" 
                        :title="'My Digital Twin'"
                        location="Te Whatu Ora"
                        description="Enables patients to interact with educational tools and their digital twins"
                        @on-explore="handleExploreClicked"
                    />
                </v-col>
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                > 
                    <DashboardCard 
                        :src="mydigitaltwinNavImage" 
                        :title="'My Digital Health Navigator'"
                        location="Auckland Bioengineering Institute"
                        description="Interact with your digital health navigator (DiNa)"
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="annotatorImage" 
                        :title="'Medical Image Annotation'"
                        location="Auckland Bioengineering Institute"
                        description="Efficiently Annotate Medical Images using Advanced AI-assisted Workflows"
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
import tutorialImage from '@/assets/dashboard/how-to-use.png';
import mydigitaltwinImage from '@/assets/dashboard/my_digitaltwin.png'
import mydigitaltwinNavImage from '@/assets/dashboard/my-digital-twin-nav.jpg'
import fcMapImage from '@/assets/dashboard/fc-map.jpg'
import annotatorImage from '@/assets/dashboard/annotator.jpg'
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
    }else if(title === "My Digital Twin"){
        window.open("https://abi-web-apps.github.io/", '_blank');
    }else if(title === "Physiology exploration (FC Map)"){
        window.open("https://mapcore-demo.org/2024/sparc-app-isan/apps/maps?id=f2a99cd3", '_blank');
    }else if(title === "My Digital Health Navigator"){
        window.open("https://www.auckland.ac.nz/en/abi.html", '_blank')
    }else if(title === "Medical Image Annotation"){
        window.open("https://build-seven-iota.vercel.app/#/", '_blank')
    }
    else {
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
    width: 90%;
}

</style>