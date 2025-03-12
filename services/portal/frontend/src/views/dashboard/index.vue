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
        <div 
            v-show="currentCategory === 'Assays'"
            class="position-fixed custom-switch">
            <v-switch
                v-model="pageSwitchModel"
                :label="`Switch to ${pageSwitchModel?'Researcher View':'Clinician View'}`"
                hide-details
                inset
                @update:model-value="(val)=>handleSwitchModel(val)"
            ></v-switch>
        </div>
        <v-card v-if="currentCategory !== 'Programmes' && currentCategory !== ''" class="position-fixed intro d-flex flex-column overflow-y-auto justify-space-around pa-5" color="transparent">
            <v-card-text>
                <div v-for="c in detailsRenderItems.categories" :key="c.name" class="text-grey-lighten-3 my-2">
                    <span v-if="c.category==='Studies'" class="font-weight-medium text-body-1">Study: </span>
                    <span v-else class="font-weight-medium text-body-1">{{ c.category.slice(0, -1) }}: </span>
                    <span class="text-body-2 tooltip-panel">
                        {{c.name}} 
                        <v-icon
                            color="blue-darken-1"
                            icon="mdi-information-outline"
                            class="ml-1"
                            size="small"
                            ></v-icon>
                        <v-tooltip
                            activator="parent"
                            location="bottom"
                            max-width="300"
                        >
                            {{ c.description }}
                        </v-tooltip>
                    </span>
                </div>
            </v-card-text>
        </v-card>

        <div  class="basic-card-container w-100 mt-16 d-flex flex-column justify-center  align-center ">
            <div v-if="showBasicCard" class="w-75 d-flex flex-wrap px-6 mt-10 justify-center align-center overflow-y-auto">
                <BasicCard v-for="data in currentCategoryData" :key="data.name" :data="data">
                    <template v-slot:action>
                        <v-btn
                            v-show="data.category !== 'Assays'"
                            color="pink-darken-2"
                            text="Explore"
                            variant="flat"
                            @click.once = "handleExploreClicked(data.seekId, data.name, data.category, data.description)"
                        ></v-btn>
                        <Dialog

                            :showDialog="data.category === 'Assays' && !pageSwitchModel"
                            :min="1200"
                            btnText="Edit"
                            btnColor = "deep-orange"
                            btnVariant="flat"
                            @on-open = "handleAssayEditClicked(data.seekId, data.name)"
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
                            <AssayContent v-model="currentAssayDetails" />
                        </Dialog>
           
                        <v-btn
                            v-show="data.category === 'Assays' && !!assayExecute![data.seekId] && assayExecute![data.seekId].text === 'Launch'"
                            color="green"
                            :text="'Launch'"
                            variant="flat"
                            :disabled="!allAssayDetailsOfStudy[data.seekId]?.isAssayReadyToLaunch"
                            @click.once = "handleAssayLaunchClicked(data.seekId)"
                        >
                        </v-btn>

                        <v-btn
                            v-show="data.category === 'Assays'&& !!assayExecute![data.seekId] && assayExecute![data.seekId].text === 'Monitor'"
                            color="green"
                            :text="'Monitor'"
                            variant="flat"
                            @click = "handleAssayMonitorClicked(data.seekId)"
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
import { useDashboardPageStore } from '@/store/states';
import { useDashboardGetAssayDetails, useDashboardGetAssayLaunch } from "@/plugins/dashboard_api";
import { useDashboardProgrammesStore, useDashboardCategoryChildrenStore, useDashboardSaveAssayDetailsStore } from '@/store/dashboard_store';
import { dashboardData, workflowsData } from "./mockData";
import { IStudy, IDashboardData, ICategoryNode,IStudiesNode } from "@/models/uiTypes";
import {IDashboardCategory, IAssayDetails} from "@/models/apiTypes";
import StudyCard from './components/StudyCard.vue';
import BasicCard from './components/BasicCard.vue';
import Dialog from '@/components/commonBar/Dialog.vue';
import AssayContent from './components/AssayContent.vue';



const router = useRouter();
const route = useRoute();
const { user } = useUser();
const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const { getTumourStudyDetails } = useTumourStudyDetailsStore();
const { dashboardProgrammes } = storeToRefs(useDashboardProgrammesStore());
const { getDashboardProgrammes } = useDashboardProgrammesStore();
const { dashboardCategoryChildren } = storeToRefs(useDashboardCategoryChildrenStore());
const { getDashboardCategoryChildren } = useDashboardCategoryChildrenStore();
const { saveAssayDetails } = useDashboardSaveAssayDetailsStore();

const {
    currentCategory, 
    breadCrumbsCategory, 
    exploredCard, 
    currentCategoryData, 
    breadCrumbsItems,
    detailsRenderItems,
    assayExecute, 
    allAssayDetailsOfStudy, 
    currentAssayDetails,
    switchModel
 } = storeToRefs(useDashboardPageStore());
const {
    setCurrentCategory, 
    setBreadCrumbsCategory, 
    setExploredCard, 
    setCurrentCategoryData, 
    setBreadCrumbsItems, 
    setDetailsRenderItems,
    setAssayExecute,
    setAllAssayDetailsOfStudy, 
    setCurrentAssayDetails,
    setSwitchModel
} = useDashboardPageStore();

const showBasicCard = ref(true);
const studyCardItems = ref<IStudiesNode[]>([]);

const breadCrumbs = ["Programmes", "Projects", "Investigations", "Studies", "Assays"];
const pageSwitchModel = ref(switchModel.value);
const isSwitchClicked = ref(false);


const handleBreadCrumbsClick = (res:PointerEvent) => {
    showBasicCard.value = true;
    const clickedCrumb = (res.target as HTMLElement).innerText;

    if (clickedCrumb === "Assays" || clickedCrumb === "/" || clickedCrumb === currentCategory.value) {
        return
    }
    // currentCategory.value = clickedCrumb;
    setCurrentCategory(clickedCrumb);
    const data = exploredCard.value.find(item => item.category === clickedCrumb)?.data;
    if (!!data) {
        setCurrentCategoryData(data);
    }else{
        setCurrentCategoryData(dashboardProgrammes.value!);
    }
    
    const index =  breadCrumbsItems.value.findIndex(item => item.title === clickedCrumb);
    const detailsIndex = detailsRenderItems.value.categories.findIndex(item => item.category === clickedCrumb);
    
    if (index !== 0) {
        setBreadCrumbsCategory(breadCrumbsItems.value[index-1].title);
        setDetailsRenderItems(detailsRenderItems.value.categories.slice(0, detailsIndex), detailsRenderItems.value.categories[detailsIndex-1].description)
    }else{
        setBreadCrumbsCategory(clickedCrumb);
        setDetailsRenderItems([], "");
    }
    breadCrumbsItems.value.splice(index+1)
}

const handleAssayEditClicked = async (seek_id:string, name:string) => {
    setCurrentAssayDetails(allAssayDetailsOfStudy.value[seek_id])
}

const handleAssaySave = async () => {
    currentAssayDetails.value!.isAssayReadyToLaunch = true;
    setAllAssayDetailsOfStudy(currentAssayDetails.value!.seekId, currentAssayDetails.value!);
    // const blob = new Blob([JSON.stringify(currentAssayDetails.value, null, 2)], { type: "application/json" });
    // const link = document.createElement("a");
    // link.href = URL.createObjectURL(blob);
    // link.download = "data.json";
    // document.body.appendChild(link);
    // link.click();
    // document.body.removeChild(link);

    
    await saveAssayDetails(currentAssayDetails.value!);
}

const handleAssayMonitorClicked = async (seek_id:string) => {
    console.log(seek_id);
    window.open(assayExecute.value![seek_id].url, '_blank');
}

const handleAssayLaunchClicked = async (seek_id:string) => {
    const res = await useDashboardGetAssayLaunch(seek_id);
    if (res.type === "airflow"){
        setAssayExecute(seek_id, "Monitor", res.data);
    }else if (res.type === "gui"){
        if (!!res.data){
            router.push({name: res.data});
        }
    }
}

const handleExploreClicked = async (seek_id:string, name:string, category:string, des:string) => {
    isSwitchClicked.value = false;
    const explored = exploredCard.value.find(item => item.category === category);
    if (!explored) setExploredCard(category, currentCategoryData.value);
    detailsRenderItems.value.categories.push({category: category, name: name, description: des});
    detailsRenderItems.value.description = des;

    setBreadCrumbsCategory(category);

    // const data = filterData.find(item => (item as ICategoryNode).category === category && (item as ICategoryNode).name === name);
    // if (category === "SOP"){
    //     showBasicCard.value = false;
    //     currentCategory.value = (data as ICategoryNode)!.name;
    //     breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });
    //     studyCardItems.value = (data as ICategoryNode)!.children as IStudiesNode[];
    //     if(currentCategory.value === "Tumour Position Study") {
    //         const completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
    //         const assistedCompleteTask = studyDetails.value?.details.filter(detail => detail.report.assisted === true);
    //         const assistedTaskCount = studyDetails.value?.details.filter(detail => detail.report.complete === true);
    //         const tumourCenterConpleteTasks = studyDetails.value?.details?.filter(detail => detail.tumour_window.validate === true);
    //         studyCardItems.value[0].studies[0].subTitle = `Completed Cases: ${completeTask!.length} / ${studyDetails.value?.details.length}`;
    //         studyCardItems.value[0].studies[1].subTitle = `Completed Cases: ${tumourCenterConpleteTasks!.length} / ${studyDetails.value?.details.length}`;
    //         studyCardItems.value[1].studies[0].subTitle = `Completed Cases: ${assistedCompleteTask!.length} / ${assistedTaskCount!.length}`;
    //     }
    //     return
    // }
    // currentCategory.value = ((data as ICategoryNode)!.children[0]  as ICategoryNode).category;
    const index = breadCrumbs.findIndex(item => item === category);
    setCurrentCategory(breadCrumbs[index+1]);
    breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });
    
    await getDashboardCategoryChildren(seek_id, category);
    setCurrentCategoryData(dashboardCategoryChildren.value!);
}

watch(()=>currentCategoryData.value, (newVal)=>{
    if(isSwitchClicked.value) return;
    if(newVal[0].category === "Assays"){
        assayExecute.value = {};
        allAssayDetailsOfStudy.value = {};
        currentCategoryData.value.forEach( async (item) => {
            const details = await useDashboardGetAssayDetails(item.seekId);
            setAssayExecute(item.seekId, "Launch", "");
            if (!!details) {
                setAllAssayDetailsOfStudy(item.seekId, details);
                
            }else{
                setAllAssayDetailsOfStudy(item.seekId, {
                    uuid: "",
                    seekId: item.seekId,
                    workflow:{
                        uuid: "",
                        seekId: "",
                        inputs: [],
                        outputs: [],
                    },
                    numberOfParticipants: 0,
                    isAssayReadyToLaunch: false,
                });
            }
        })
    }
})

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

const handleSwitchModel = (val:boolean|null) => {
    console.log(val);
    
    setSwitchModel(val as boolean);
    isSwitchClicked.value = true;
    if (val){
        let i = 0;
        const a:any[] = [];
        currentCategoryData.value.map(item => {
            if (val && i>2){
                a.push(item);
            }
            i +=1;
        })
        currentCategoryData.value = a;
    }else{
        setCurrentCategoryData(dashboardCategoryChildren.value!);
    }
   
}

onMounted(async () => {
    if (!user.value) router.push({name: 'Login'});
    if (!!studyDetails.value === false) await getTumourStudyDetails();
    await getDashboardProgrammes();
    if (currentCategoryData.value.length === 0)
        currentCategoryData.value = dashboardProgrammes.value!;
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
    width: 20%;
/* 
    border-radius: 6px;
    box-shadow:  1px 1px 5px #d3d3d3,
                -1px -1px 5px #d3d3d3; */
}
.basic-card-container{
    height: 80%;
}
.tooltip-panel{
    cursor: help;
}
.custom-switch{
    top: 20%;
    right: 100px;
}
</style>