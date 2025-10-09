<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <div class="main-container overflow-y-auto">
             <div class="my-2">
                <h3 class="mb-2">About</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    
                </div>
            </div>

            <div class="my-2">
                <h3 class="mb-2">Help documentation</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    <SimpleInfoCard 
                        v-for="(h, i) in helps"
                        class="mx-2"
                        :key="i"
                        :herf=h.herf
                        :title=h.title
                        :width=h.width
                    />
                </div>
            </div>
            
            <div class="my-2">
                <h3 class="mb-2">API documentation</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    <SimpleInfoCard 
                        v-for="(a, i) in apiDocs"
                        class="mx-2"
                        :key="i"
                        :herf=a.herf
                        :title=a.title
                        :width=a.width
                    />
                </div>
            </div>
            
            <div class="my-2">
                <h3 class="mb-2">Guidelines</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    <SimpleInfoCard 
                        v-for="(a, i) in guidelines"
                        class="mx-2"
                        :key="i"
                        :herf=a.herf
                        :title=a.title
                        :width=a.width
                    />
                </div>
            </div>

            <div class="my-2">
                <h3 class="mb-2">Resources</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    <SimpleInfoCard 
                        v-for="(a, i) in resources"
                        class="mx-2"
                        :key="i"
                        :herf=a.herf
                        :title=a.title
                        :width=a.width
                    />
                </div>
            </div>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/components/dt-components/SimpleInfoCard.vue';
// import NavHome from '@/views/dashboard/components/NavHome.vue';
import {h, ref} from 'vue'

const helps = [
    {
        "title":"How to use the study dashboard",
        "herf":"https://github.com/ABI-CTT-Group/DigitalTWINS-Portal?tab=readme-ov-file#how-to-use-the-study-dashboard",
        "width":350,
    },
    {
        "title":"How to create and upload datasets",
        "herf":"https://copper3d-brids.github.io/ehr-docs/docs/ehr/literature-review/data%20de-identification#de-identifying-dicom-data-with-hipaa",
        "width":350,
    }
]

const apiDocs = [
    {
        title:"DigitalTWINS-API",
        herf:"http://130.216.217.184:8010/docs",
        width:350,
    },
    {
        title:"DigitalTWINS-Portal-API",
        herf:"http://130.216.217.176:8000/docs",
        width:350,
    }
]

const guidelines = [
    {
        title:"Computational physiology workflows",
        herf:"https://docs.google.com/document/d/1ArbBXdzKCbM_ED5fDBR9yqC2KGp-1Hl7wrrV29ABB1k/edit?tab=t.0#heading=h.c87qz8f8iu38",
        width:350
    }
]

const resources = ref([
    {
        title:"DigitalTWINS on FHIR",
        herf:"https://colab.research.google.com/drive/15c_v9sK4wSF3Rng3j6xk-L6ngfWEEbPq",
        width:350
    },
    {
        title:"Clinical Description Annotator",
        herf:"https://colab.research.google.com/drive/1rMgA9ycJHyQ1owI-vRyIquIVOU5eAjIF#scrollTo=oAw8vVmP2AWj",
        width:350
    },
    {
        title:"Sparc-me",
        herf:"https://github.com/SPARC-FAIR-Codeathon/sparc-me/tree/main?tab=readme-ov-file#sparc-metadata-editor-sparc-me",
        width:350
    },
])

</script>

<style scoped>

.main-container{
    width: 80%;
    margin-top: 100px;
    margin-bottom: 20px;
    padding: 50px;
    height: 90%;
    background: rgba(1, 62, 62, 0.15); 
    /* border: 1px solid rgba(255, 255, 255, 0.125); */
    border-radius: 10px !important;
    box-shadow:  5px 5px 10px #071b25,
             -5px -5px 10px #0d3547 !important;
}
</style>