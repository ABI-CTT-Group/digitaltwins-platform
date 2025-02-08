<template>
    <div class="w-screen h-screen gradients d-flex flex-column align-center">
        <h1 class="text-center py-4 text-grey-lighten-2">Clinical Study Dashboard</h1>
        <v-divider :thickness="3" class="w-100"></v-divider>
        <div class="position-fixed breadcrumbs d-flex justify-start align-center w-75">
            <v-breadcrumbs
                class="custom-pointer"
                :items="breadCrumbsItems"
                divider="/"
                @click="handleBreadCrumbsClick"
            ></v-breadcrumbs>
        </div>

        <div v-if="detailsRenderItems.description !== ''" class="position-fixed intro d-flex flex-column overflow-y-auto justify-space-around pa-5 ">
            <div>
                <div v-for="c in detailsRenderItems.categories" :key="c.name" class="text-grey-darken-3 my-2">
                    <span v-if="c.category==='Studies'" class="font-weight-medium text-body-1">Study: </span>
                    <span v-else class="font-weight-medium text-body-1">{{ c.category.slice(0, -1) }}: </span>
                    <span class="text-body-2">{{c.name}}</span>
                </div>
            </div>
            
            <div class="mt-2 text-grey-darken-3">
                <span class="font-weight-medium text-body-1">Description: </span>
                <span class="text-body-2">{{detailsRenderItems.description}}</span>
            </div>
        </div>

        <div v-if="showBasicCard" class="h-75 w-100 mt-16 d-flex flex-column justify-center  align-center ">
            <div class="w-75 d-flex flex-wrap px-6 mt-10 justify-center align-center overflow-y-auto">
                <BasicCard v-for="data in currentCategoryData" :key="data.name" :data="data">
                    <template v-slot:action>
                        <v-btn
                            v-show="data.category !== 'Assays'"
                            color="pink-darken-2"
                            text="Explore"
                            variant="outlined"
                            @click = "handleExploreClicked(data.name, data.category, data.description)"
                        ></v-btn>
                        <Dialog
                            :showDialog="data.category === 'Assays'"
                            :min="1200"
                            btnText="Create"
                            btnColor = "deep-orange"
                            @on-open = "handleAssayCreateClicked(data.name, data.category)"
                            @on-save= "handleAssaySave"
                        >
                            <template #title>
                                <h2 class="text-h5 mb-6">Update Assay <span class="text-subtitle-1 font-weight-bold" >"{{ data.name }}"</span> </h2>
                            </template>
                            <template #description>
                                <p class="mb-4 text-medium-emphasis text-body-2">
                                    Config the assay's: workflow, dataset and cohorts. 
                                    <br/>
                                    Click `Save` button to save your configurations. Click grey area to cancel.
                                </p>
                            </template>
                            <AssayContent :workflows-data="workflowsData" />
                        </Dialog>
                        <v-btn
                            v-show="data.category === 'Assays'"
                            color="green"
                            text="Run"
                            variant="outlined"
                            :disabled="true"
                            @click = "handleAssayRunClicked(data.name, data.category)"
                        ></v-btn>
                    </template>
                </BasicCard>
                
            </div>
        </div>
        <div v-if="!showBasicCard" class="w-75 flex-1-1 px-6 d-flex justify-center align-center">
            <v-carousel 
                hide-delimiter-background
                hide-delimiters
                :show-arrows="isShowArrow"
            >
                <!-- <template v-slot:prev="{ props }">
                    <div></div>
                </template> -->
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
import { ref, onMounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useUser } from "@/plugins/hooks/user";
import { storeToRefs } from "pinia";
import { useTumourStudyDetailsStore } from "@/store/tumour_position_study_app";
import { dashboardData, workflowsData } from "./mockData";
import { IStudy, IDashboardData, ICategoryNode,IStudiesNode } from "@/models/uiTypes";
import StudyCard from './components/StudyCard.vue';
import BasicCard from './components/BasicCard.vue';
import Dialog from '@/components/commonBar/Dialog.vue';
import AssayContent from './components/AssayContent.vue';


const router = useRouter();
const route = useRoute();
const { user } = useUser();
const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const currentCategory = ref("");
const breadCrumbsCategory = ref("");
const exploredCard = ref<any[]>([]);
const showBasicCard = ref(true);
const studyCardItems = ref<IStudiesNode[]>([]);
let filterData: (ICategoryNode | IStudiesNode)[];
// const currentCategoryData = ref<ICategoryNode>();
const breadCrumbsItems = ref([
    { title: 'Programmes', disabled: false },
])
const workflowRenderItems = ref<string[]>([]);

const detailsRenderItems = ref<{
    categories: {category: string, name: string, description: string}[];
    description: string;
}>({
    categories:[],
    description: "",
})

const handleBreadCrumbsClick = (res:PointerEvent) => {
    showBasicCard.value = true;
    const clickedCrumb = (res.target as HTMLElement).innerText;
    currentCategory.value = clickedCrumb;
    const index =  breadCrumbsItems.value.findIndex(item => item.title === clickedCrumb);
    const detailsIndex = detailsRenderItems.value.categories.findIndex(item => item.category === clickedCrumb);
    
    if (index !== 0) {
        breadCrumbsCategory.value = breadCrumbsItems.value[index-1].title;
        detailsRenderItems.value.categories = detailsRenderItems.value.categories.slice(0, detailsIndex);
        
        detailsRenderItems.value.description = detailsRenderItems.value.categories[detailsIndex-1].description;
    }else{
        breadCrumbsCategory.value = clickedCrumb;
        detailsRenderItems.value.categories = [];
        detailsRenderItems.value.description = "";
    }
    breadCrumbsItems.value.splice(index+1)
}

const getWorkflowRenderData = ()=>{
    // workflowRenderItems.value = workflowsData.map(workflow => workflow.name + "-" + workflow.type);
}

const handleAssayCreateClicked = (name:string, category:string) => {
    console.log(name, category);
    getWorkflowRenderData();
}

const handleAssaySave = () => {
    console.log("Save Assay");
}

const handleAssayRunClicked = (name:string, category:string) => {
    console.log(name, category);
}

const handleExploreClicked = (name:string, category:string, des:string) => {
    const explored = exploredCard.value.find(item => item[category] === name);
    if (!explored) exploredCard.value.push({[category]: name});
    detailsRenderItems.value.categories.push({category: category, name: name, description: des});
    detailsRenderItems.value.description = des;

    breadCrumbsCategory.value = category;

    const data = filterData.find(item => (item as ICategoryNode).category === category && (item as ICategoryNode).name === name);
    if (category === "SOP"){
        showBasicCard.value = false;
        currentCategory.value = (data as ICategoryNode)!.name;
        breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });
        studyCardItems.value = (data as ICategoryNode)!.children as IStudiesNode[];
        if(currentCategory.value === "Tumour Position Study") {
            const completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
            const assistedCompleteTask = studyDetails.value?.details.filter(detail => detail.report.assisted === true);
            const assistedTaskCount = studyDetails.value?.details.filter(detail => detail.report.complete === true);
            const tumourCenterConpleteTasks = studyDetails.value?.details?.filter(detail => detail.tumour_window.validate === true);
            studyCardItems.value[0].studies[0].subTitle = `Completed Cases: ${completeTask!.length} / ${studyDetails.value?.details.length}`;
            studyCardItems.value[0].studies[1].subTitle = `Completed Cases: ${tumourCenterConpleteTasks!.length} / ${studyDetails.value?.details.length}`;
            studyCardItems.value[1].studies[0].subTitle = `Completed Cases: ${assistedCompleteTask!.length} / ${assistedTaskCount!.length}`;
        }
        return
    }
    currentCategory.value = ((data as ICategoryNode)!.children[0]  as ICategoryNode).category;
    breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });
}

// user.value === 'admin' ? 'active' : 'inactive'
// const items = ref([
//           {
//             studies:[
//                 {
//                     name: 'Tumour Position Study',
//                     subTitle: "Cases: 100",
//                     description: 'Calculate tumour distance to the skin, ribcage, and nipple mannually',
//                     src: 'https://cdn.vuetifyjs.com/images/cards/docks.jpg',
//                     status: 'active',
//                     isEnter: false,
//                     session: "TumourCalaulationStudy"
//                 },
//                 {
//                     name: 'Tumour Center Manual Correction',
//                     subTitle: "Cases: 100",
//                     description: 'Give tumour center at bounding box, and correct the center mannually',
//                     src: 'https://cdn.vuetifyjs.com/images/carousel/planet.jpg',
//                     status: user.value === 'admin' ? 'active' : 'inactive',
//                     isEnter: false,
//                     session: "TumourCenterStudy"
//                 },  
//             ],
//           },
//           {
//             studies:[ 
//                 {
//                     name: 'Tumour Study Assisted Manually',
//                     subTitle: "Cases: 100",
//                     description: 'Assist to change tumour, skin, ribcage, and nipple position',
//                     src: 'https://cdn.vuetifyjs.com/images/carousel/sky.jpg',
//                     status: user.value === 'admin' ? 'active' : 'inactive',
//                     isEnter: false,
//                     session: "TumourAssistedStudy"
//                 },
//                 {
//                     name: 'Tumour Position & Extent Report',
//                     subTitle: "Cases: 100",
//                     description: 'Using tools to segment tumour and generate a report',
//                     src: 'https://cdn.vuetifyjs.com/images/cards/sunshine.jpg',
//                     status: user.value === 'admin' ? 'active' : 'inactive',
//                     isEnter: false,
//                     session: "TumourSegmentationStudy"
//                 },
//             ],
//           }
//         ])

const currentCategoryData = computed(() => {
    if (currentCategory.value === "") return;
    if (currentCategory.value === "Programmes"){
        filterData = dashboardData;
        return dashboardData;
    }else{
        const data = getFilterData(dashboardData);
        filterData = data?.children as (ICategoryNode | IStudiesNode)[];
        return data?.children;
    }
});

const getFilterData = (categoryData:ICategoryNode[]):ICategoryNode|undefined => {
   
    for (let child of categoryData){
        const explored = exploredCard.value.find(item => item[breadCrumbsCategory.value] === child.name);
        if (!!explored) {
            return child;   
        }
        const result = getFilterData(child.children as ICategoryNode[]);
        if (result) {
            return result;
        }
    }
    return undefined;
}

const updateBreadCrumbs = (category: string) => {
    breadCrumbsItems.value = [
        { title: 'Programme', disabled: false},
        { title: category, disabled: false }
    ]
}

const renderItems = computed(() => {
    return studyCardItems.value.map(item => {
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
    currentCategory.value = "Programmes";
    if (!!studyDetails.value === false) await getTumourStudyDetails();
})

const handleStudyCardEnterClicked = (study: IStudy) => {
    studyCardItems.value.forEach(item => {
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
    

    /* background-image: linear-gradient(45deg, #8baaaa 0%, #ae8b9c 100%); */
    /* background: linear-gradient(to bottom, #323232 0%, #3F3F3F 40%, #1C1C1C 150%), linear-gradient(to top, rgba(255,255,255,0.40) 0%, rgba(0,0,0,0.25) 200%); background-blend-mode: multiply; */
    background-repeat: repeat;
    /* background: #403B4A; 
    background: -webkit-linear-gradient(to right, #E7E9BB, #403B4A); 
    background: linear-gradient(to right, #E7E9BB, #403B4A);  */

}
.breadcrumbs {
    top: 110px;
    border-radius: 5% 95% 97% 3% / 42% 45% 55% 58%  ;
    box-shadow:  8px 8px 10px  #636363,
                -8px -8px 10px #878787;
}
.custom-pointer {
  cursor: pointer !important;
}

.intro{
    top: 30%;
    left: 5px;
    width: 18%;

    border-radius: 6px;
    box-shadow:  1px 1px 5px #d3d3d3,
                -1px -1px 5px #d3d3d3;
}
</style>