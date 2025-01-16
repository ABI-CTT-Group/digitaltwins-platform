<template>
    <div class="w-screen h-screen gradients d-flex flex-column align-center">
        <h1 class="text-center pt-10">Clinical Study Dashboard</h1>

        <div class="w-75 flex-1-1 px-6 d-flex justify-center align-center">
            <v-carousel 
                hide-delimiter-background
                hide-delimiters
                show-arrows
            >
                <template v-slot:prev="{ props }">
                    <div></div>
                </template>
                <v-carousel-item
                v-for="(item,i) in renderItems"
                :key="i"
                cover
                >
                    <div class="w-100 h-100 d-flex justify-space-evenly align-center">
                        <div v-for="study in item.studies">
                            <v-card
                                class="mx-auto"
                                max-width="350"
                                min-width="350"
                            >
                                <v-img
                                    class="align-end text-white"
                                    height="200"
                                    :src="study.src"
                                    cover
                                >
                                    <v-card-title>{{ study.title }}</v-card-title>
                                </v-img>
                                <v-card-subtitle class="pt-4">
                                    {{ study.subTitle }}
                                </v-card-subtitle>

                                <v-card-text>
                                    <div>{{ study.description }}</div>
                                </v-card-text>

                                <v-card-actions>
                                    <v-btn v-if="!study.isEnter" color="green" text="Enter" @click="handleEnter(study)"></v-btn>
                                    <v-btn v-if="study.isEnter" color="orange" text="Begin session" @click="handleStartSession(study.session)"></v-btn>
                                    <v-btn v-if="study.isEnter" color="orange" text="Tutorial"></v-btn>
                                </v-card-actions>
                            </v-card>
                        </div>
                        
                    </div>
                </v-carousel-item>
            </v-carousel>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useUser } from "@/plugins/hooks/user";
import { storeToRefs } from "pinia";
import { useTumourStudyDetailsStore } from "@/store/tumour_position_study_app";
const router = useRouter();
const route = useRoute();
const { user } = useUser();

const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();

type Study = {
    title: string;
    subTitle: string;
    description: string;
    src: string;
    status: string;
    isEnter: boolean;
    session: string;
}

const items = ref([
          {
            studies:[
                {
                    title: 'Tumour Position Study',
                    subTitle: "Cases: 100",
                    description: 'Calculate tumour distance to the skin, ribcage, and nipple mannually',
                    src: 'https://cdn.vuetifyjs.com/images/cards/docks.jpg',
                    status: 'active',
                    isEnter: false,
                    session: "TumourCalaulationStudy"
                },
                {
                    title: 'Tumour Center Manual Correction',
                    subTitle: "Cases: 100",
                    description: 'Give tumour center at bounding box, and correct the center mannually',
                    src: 'https://cdn.vuetifyjs.com/images/carousel/squirrel.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: "TumourCenterStudy"
                },  
            ],
          },
          {
            studies:[
                {
                    title: 'Tumour Position & Extent Report',
                    subTitle: "Cases: 100",
                    description: 'Using tools to segment tumour and generate a report',
                    src: 'https://cdn.vuetifyjs.com/images/cards/sunshine.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: "TumourSegmentationStudy"
                },
                {
                    title: 'Study 4',
                    subTitle: "Cases: 100",
                    description: 'This is a description of study 4',
                    src: 'https://cdn.vuetifyjs.com/images/carousel/sky.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: ""
                },
            ],
          }
        ])

const renderItems = computed(() => {
    return items.value.map(item => {
        return {
            ...item,
            studies: item.studies.filter(study => study.status === 'active')
        }
    })
})

onMounted(async () => {
    if (!!studyDetails.value === false) await getTumourStudyDetails();
    const completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
    items.value[0].studies[0].subTitle = `Completed Cases: ${completeTask!.length} / ${studyDetails.value?.details.length}`;
})
const handleEnter = (study: Study) => {
    study.isEnter=!study.isEnter
    items.value.forEach(item => {
        item.studies.forEach(s => {
            if (s !== study) {
                s.isEnter = false
            }
        })
    })   
}

const handleStartSession = (session: string) => {
    if (session === "") return;
    router.push({name: session})
}
</script>

<style scoped>
.gradients {
    background: #556270;  
    background: -webkit-linear-gradient(to right, #FF6B6B, #556270);  
    background: linear-gradient(to right, #FF6B6B, #556270); 

    /* background: #403B4A; 
    background: -webkit-linear-gradient(to right, #E7E9BB, #403B4A); 
    background: linear-gradient(to right, #E7E9BB, #403B4A);  */

}
</style>