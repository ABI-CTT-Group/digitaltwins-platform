<template>
    <div class="container overflow-hidden d-flex justify-center">
        <div class="overflow-y-auto sub-container">
            <Hero >
                 <v-btn
                    color="green-lighten-2"
                    class="text-sky-900 px-6 py-3"
                    size="large"
                    elevation="6"
                    rounded="xl"
                    variant="tonal"
                    @click="handleHeroStarted"
                >
                    Get Started
                </v-btn>
                <v-btn
                    color="purple-lighten-2"
                    class="text-white px-6 py-3"
                    size="large"
                    elevation="6"
                    rounded="xl"
                    variant="tonal"
                    @click="handleHeroDocumentation"
                >
                    Documentation
                </v-btn>
            </Hero>
            <v-row class="cards">
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                >
                    <DashboardCard 
                        :src="tutorialImage" 
                        :title="'How to use this platform'"
                        location="Auckland Bioengineering Institute"
                        description="Provides help and tutorials describing how to use the platform."
                        @on-explore="handleExploreClicked"
                        />    
                    <DashboardCard 
                        :src="catelogueImage" 
                        :title="'Catalogue'"
                        location="Auckland Bioengineering Institute"
                        description="Provides “yellow pages” that enable users to see what AI/digital twin assets are being developed in research programmes. This includes viewing or adding new programmes, projects, investigations, studies, assays, workflows, measurements, and models."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="studyImage" 
                        :title="'Study dashboard'"
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
                        :src="clinicalImage"
                        :title="'Clinician dashboard'"
                        location="Te Whatu Ora AI Lab"
                        description="Enables clinicians to run AI/digital twin driven workflows and generate clinical reports."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="fcMapImage" 
                        :title="'Physiology exploration (FC Map)'"
                        location="SPARC"
                        description="Use the FC Map to explore physics informed biomedical models."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="mydigitaltwinImage" 
                        :title="'My digital twin'"
                        location="Te Whatu Ora"
                        description="Enables patients to interact with their digital twins to better understand and manage their medical conditions."
                        @on-explore="handleExploreClicked"
                    />
                </v-col>
                <v-col
                    cols="12"
                    md="12"
                    class="d-flex justify-space-around align-center"
                > 
                    <DashboardCard 
                        :src="digitalRepositoryImage" 
                        :title="'DigitalTWINS data repository'"
                        location="Auckland Bioengineering Institute"
                        description="World’s first data resource where health information from participants across multiple research studies can be contributed, linked, and reused with informed consent for developing digital twins."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="mydigitaltwinNavImage" 
                        :title="'My digital health navigator'"
                        location="Auckland Bioengineering Institute"
                        description="Interact with your digital health navigator (DiNa)."
                        @on-explore="handleExploreClicked"
                    />
                    <DashboardCard 
                        :src="annotatorImage" 
                        :title="'Medical image annotation'"
                        location="Auckland Bioengineering Institute"
                        description="Efficiently annotate medical images using advanced AI-assisted workflows."
                        @on-explore="handleExploreClicked"
                    />
                </v-col>
            </v-row>
        </div>
        
    </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import DashboardCard from '@/components/dt-components/DashboardCard.vue';
import Hero from '@/components/dt-components/Hero.vue';
import clinicalImage from '@/assets/dashboard/clinical-01.jpg';
import studyImage from '@/assets/dashboard/study.png';
import catelogueImage from '@/assets/dashboard/catalogue.png';
import tutorialImage from '@/assets/dashboard/how-to-use.png';
import mydigitaltwinImage from '@/assets/dashboard/my_digitaltwin.png'
import mydigitaltwinNavImage from '@/assets/dashboard/my-digital-twin-nav.jpg'
import fcMapImage from '@/assets/dashboard/fc-map.jpg'
import annotatorImage from '@/assets/dashboard/annotator.jpg'
import digitalRepositoryImage from '@/assets/dashboard/digital-repository.jpg'
import { useRouter, useRoute } from 'vue-router';
import { useDashboardPageStore } from '@/store/states';

const router = useRouter();

onMounted(() => {
    localStorage.removeItem("dashboardPage");
    // const dashboardStore = useDashboardPageStore();
    // dashboardStore.$reset();
});

const handleExploreClicked = (title: string) => {
   
    if(title === 'Study dashboard') {
        router.push({name:'Dashboard', params: { dashboardType: 'study' }});
    } else if(title === 'Clinician dashboard') {
        router.push({name:'Dashboard', params: { dashboardType: 'clinician' }});
    }else if(title === 'Catalogue') {
        router.push({name:"CatalogueDashboardView"})
    }else if(title === "How to use this platform"){
        router.push({name:'TutorialDashboard'});
    }else if(title === "My digital twin"){
        window.open("https://abi-web-apps.github.io/", '_blank');
    }else if(title === "Physiology exploration (FC Map)"){
        window.open("https://mapcore-demo.org/2024/sparc-app-isan/apps/maps?id=f2a99cd3", '_blank');
    }else if(title === "My digital health navigator"){
        window.open("https://dina.kekayan.com/", '_blank')
    }else if(title === "Medical image annotation"){
        window.open("https://build-seven-iota.vercel.app/#/", '_blank')
    }
    else {
        console.log(`Unknown title: ${title}`);
    }
}

const handleHeroStarted = () => {
     router.push({name:'Dashboard', params: { dashboardType: 'clinician' }});
}

const handleHeroDocumentation = () => {
    router.push({name:'TutorialDashboard'});
}
</script>

<style scoped>

.sub-container{
    width: 90%;
    margin-top: 70px;
}

</style>