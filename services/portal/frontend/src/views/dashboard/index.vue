<template>
    <div class="w-screen h-screen gradients d-flex flex-column align-center">
        <h1 class="text-center pt-10 ">Clinical Study Dashboard</h1>
        <div class="position-fixed breadcrumbs d-flex justify-start align-center w-75 pt-5">
            <v-breadcrumbs
                :items="breadCrumbsItems"
                divider="/"
                @click="handleBreadCrumbsClick"
            ></v-breadcrumbs>
        </div>
        
        <div class="w-75 flex-1-1 px-6 d-flex justify-center align-center">
            <v-carousel 
                hide-delimiter-background
                hide-delimiters
                :show-arrows="isShowArrow"
            >
                <template v-slot:prev="{ props }">
                    <div></div>
                </template>
                <v-carousel-item
                    v-for="(item,i) in renderItems"
                    :key="i"
                    cover
                >
                    <div  class="w-100 h-100 d-flex justify-space-evenly align-center">
                        <div v-for="study in item.studies">
                            <StudyCard :study="study" @update:enter-clicked="handleStudyCardEnterClicked"/>
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
import { dashboardData } from "./mockData";
import { IStudy, IDashboardData, ICategoryNode } from "@/models/uiTypes";
import StudyCard from './components/StudyCard.vue';


const router = useRouter();
const route = useRoute();
const { user } = useUser();
const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const currentCategory = ref("Dashboard");
const currentCategoryData = ref<ICategoryNode>();
const breadCrumbsItems = ref([
    { title: 'Home', disabled: false },
    { title: 'Programme', disabled: false },
])

const handleBreadCrumbsClick = (res:PointerEvent) => {
    const clickedCrumb = (res.target as HTMLElement).innerText;
    const index =  breadCrumbsItems.value.findIndex(item => item.title === clickedCrumb);
    breadCrumbsItems.value.splice(index+1)
}

// user.value === 'admin' ? 'active' : 'inactive'
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
                    src: 'https://cdn.vuetifyjs.com/images/carousel/planet.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: "TumourCenterStudy"
                },  
            ],
          },
          {
            studies:[ 
                {
                    title: 'Tumour Study Assisted Manually',
                    subTitle: "Cases: 100",
                    description: 'Assist to change tumour, skin, ribcage, and nipple position',
                    src: 'https://cdn.vuetifyjs.com/images/carousel/sky.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: "TumourAssistedStudy"
                },
                {
                    title: 'Tumour Position & Extent Report',
                    subTitle: "Cases: 100",
                    description: 'Using tools to segment tumour and generate a report',
                    src: 'https://cdn.vuetifyjs.com/images/cards/sunshine.jpg',
                    status: user.value === 'admin' ? 'active' : 'inactive',
                    isEnter: false,
                    session: "TumourSegmentationStudy"
                },
            ],
          }
        ])

// const items = computed(() => {
//     switch (currentCategory.value) {
//         case "Programme":
//             return dashboardData;
    
//         default:
//             return dashboardData;
//     }
// });

const updateBreadCrumbs = (category: string) => {
    breadCrumbsItems.value = [
        { title: 'Programme', disabled: false},
        { title: category, disabled: false }
    ]
}

const renderItems = computed(() => {
    return items.value.map(item => {
        // if (item.name === "Programme"){
        //     breadCrumbsItems
        // }
        return {
            ...item,
            studies: item.studies.filter(study => study.status === 'active')
        }
    })
})
const isShowArrow = computed(() => {
    return renderItems.value.length > 1 ? true : false;
});

onMounted(async () => {
    if (!user.value) router.push({name: 'Login'});
    

    if (!!studyDetails.value === false) await getTumourStudyDetails();
    const completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
    const assistedCompleteTask = studyDetails.value?.details.filter(detail => detail.report.assisted === true);
    const assistedTaskCount = studyDetails.value?.details.filter(detail => detail.report.complete === true);
    const tumourCenterConpleteTasks = studyDetails.value?.details?.filter(detail => detail.tumour_window.validate === true);
    items.value[0].studies[0].subTitle = `Completed Cases: ${completeTask!.length} / ${studyDetails.value?.details.length}`;
    items.value[0].studies[1].subTitle = `Completed Cases: ${tumourCenterConpleteTasks!.length} / ${studyDetails.value?.details.length}`;
    items.value[1].studies[0].subTitle = `Completed Cases: ${assistedCompleteTask!.length} / ${assistedTaskCount!.length}`;
})

const handleStudyCardEnterClicked = (study: IStudy) => {
    items.value.forEach(item => {
        item.studies.forEach(s => {
            if (s !== study) {
                s.isEnter = false
            }
        })
    })
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
.breadcrumbs {
    top: 100px
}
</style>