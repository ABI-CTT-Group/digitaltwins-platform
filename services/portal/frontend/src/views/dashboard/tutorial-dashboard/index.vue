<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <NavHome>
            <h1 class="mx-auto">How it works</h1>
        </NavHome>
        <div class="main-container overflow-y-auto">
            <v-row justify="center">
                <v-col
                    v-for="(t, i) in tutorials"
                    :key="i"
                    cols="12"
                    md="4"
                >
                    <SimpleInfoCard 
                        category="Tutorial"
                        :herf=t.herf
                        :title=t.title
                        :description=t.description
                    />
                </v-col>
            </v-row>
        </div>
    </div>
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/views/dashboard/components/SimpleInfoCard.vue';
import NavHome from '@/views/dashboard/components/NavHome.vue';
import {ref} from 'vue'

const tutorials = ref([
    {
        title:"DigitalTWINS on FHIR",
        description:"DigitalTWINs on FHIR uses FHIR R4 to integrate EHR and research data via a structured specification.",
        herf:"https://colab.research.google.com/drive/15c_v9sK4wSF3Rng3j6xk-L6ngfWEEbPq"
    },
    {
        title:"Clinical Description Annotator",
        description:"Annotator for converting SPARC SDS measurement and workflow data into the DigitalTwins-on-FHIR required format.",
        herf:"https://colab.research.google.com/drive/1rMgA9ycJHyQ1owI-vRyIquIVOU5eAjIF#scrollTo=oAw8vVmP2AWj"
    },
    {
        title:"Sparc-me",
        description:"A python tool to explore, enhance, and expand SPARC datasets and their descriptions in accordance with FAIR principles.",
        herf:"https://github.com/SPARC-FAIR-Codeathon/sparc-me/tree/main/examples"
    },
])

</script>

<style scoped>
.container{
  /* background: #556270;   */
  /* background-color: #424242; */
  background: #556270;  
  background: -webkit-linear-gradient(to right, #FF6B6B, #556270);  
  background: linear-gradient(to right, #FF6B6B, #556270); 
}
.main-container{
    width: 80%;
    padding-top: 100px;
    height: 95%;
}
</style>