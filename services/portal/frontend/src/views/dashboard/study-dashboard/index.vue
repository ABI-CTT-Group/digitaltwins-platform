<template>
    <div class="w-screen h-screen container d-flex flex-column align-center">
        <NavHome>
            <h1 class="text-center py-4 text-grey-lighten-2">{{title}} Dashboard</h1>
        </NavHome>
        <div class="position-fixed breadcrumbs d-flex justify-start align-center w-75">
            <v-breadcrumbs
                class="custom-pointer"
                :items="breadCrumbsItems"
                divider="/"
                @click="handleBreadCrumbsClick"
            ></v-breadcrumbs>
        </div>
        <!-- <div 
            v-show="currentCategory === 'Assays'"
            class="position-fixed custom-switch">
            <v-switch
                v-model="pageSwitchModel"
                :label="`Switch to ${pageSwitchModel?'Researcher View':'Clinician View'}`"
                hide-details
                inset
                @update:model-value="(val:boolean|null)=>handleSwitchModel(val)"
            ></v-switch>
        </div> -->
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

        <div  class="basic-card-container w-100 d-flex flex-column justify-center align-center ">
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
                            :showDialog="data.category === 'Assays' && !isClinicianView"
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
                        <!-- <v-btn
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
                        ></v-btn> -->
                        <div class="d-flex ga-2 justify-center" v-if="data.category === 'Assays'">
                            <v-btn
                                color="green"
                                :text="'Launch'"
                                variant="flat"
                                :width="100"
                                :disabled="!allAssayDetailsOfStudy[data.seekId]?.isAssayReadyToLaunch"
                                @click.once = "handleAssayLaunchClicked(data.seekId)"
                            >
                            </v-btn>
                            <v-btn
                                color="green"
                                :text="'Monitor'"
                                variant="flat"
                                :width="100"
                                :disabled="!(data.category === 'Assays'&& !!assayExecute![data.seekId] && assayExecute![data.seekId].text === 'Monitor')"
                                @click = "handleAssayMonitorClicked(data.seekId)"
                            >
                            </v-btn>
                            <v-btn
                                color="green"
                                :text="'Verify'"
                                variant="flat"
                                :width="100"
                                :disabled="!allAssayDetailsOfStudy[data.seekId]?.isAssayReadyToLaunch"
                                @click = "handleAssayVerifyClicked(data.seekId)"
                            ></v-btn>
                            <v-btn
                                color="green"
                                :text="'Download'"
                                variant="flat"
                                :width="100"
                                :disabled="!allAssayDetailsOfStudy[data.seekId]?.isAssayReadyToLaunch"
                                @click = "handleAssayDownloadClicked(data.seekId)"
                            ></v-btn>
                            <v-btn
                                color="green"
                                :text="'Upload'"
                                variant="flat"
                                :width="100"
                                :disabled="!allAssayDetailsOfStudy[data.seekId]?.isAssayReadyToLaunch"
                                @click = "handleAssayUploadClicked(data.seekId)"
                            ></v-btn>
                        </div>
                        
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
        <DownloadSheet :download-zip-progress-value="downloadZipProgressValue" v-model:download-dialog="downloadDialog"></DownloadSheet>
        <UploadSheet v-model:upload-dialog="uploadDialog" :upload-state="uploadState" />
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
import { dashboardData, workflowsData } from "../mockData";
import { IStudy, IDashboardData, ICategoryNode,IStudiesNode } from "@/models/uiTypes";
import {IDashboardCategory, IAssayDetails} from "@/models/apiTypes";
import StudyCard from '@/views/dashboard/components/StudyCard.vue';
import BasicCard from '@/views/dashboard/components/BasicCard.vue';
import Dialog from '@/components/commonBar/Dialog.vue';
import AssayContent from '@/views/dashboard/components/AssayContent.vue';
import NavHome from '@/views/dashboard/components/NavHome.vue';
import axios from 'axios';
import DownloadSheet from '../components/DownloadSheet.vue';
import UploadSheet from '../components/UploadSheet.vue';

const username = 'admin';
const password = 'ctt_digitaltwins_0';


const router = useRouter();
const route = useRoute();

const title = route.params.dashboardType === "study" ? "Study" : "Clinician";
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
    isClinicianView
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
    setClinicianView
} = useDashboardPageStore();

const showBasicCard = ref(true);
const studyCardItems = ref<IStudiesNode[]>([]);

const breadCrumbs = ["Programmes", "Projects", "Investigations", "Studies", "Assays"];
// const isSwitchClicked = ref(false);

const downloadZipProgressValue = ref(0);
const downloadDialog = ref(false);
const uploadDialog = ref(false);
const uploadState = ref("waiting");

const handleBreadCrumbsClick = (res:PointerEvent) => {
    showBasicCard.value = true;
    const clickedCrumb = (res.target as HTMLElement).innerText;

    if (clickedCrumb === "Assays" || clickedCrumb.includes("/") || clickedCrumb === currentCategory.value) {
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
    await saveAssayDetails(currentAssayDetails.value!);
}

const handleAssayUploadClicked = async (assay_seek_id:string) => {
    uploadDialog.value = true
    uploadState.value = "waiting"
     axios.get('http://130.216.208.137:8089/upload_workflow_outputs/22', {
        auth: {
            username: username,
            password: password
        }
        })
        .then(response => {
            uploadState.value = String(response.data) 
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

const handleAssayDownloadClicked = async (assay_seek_id:string) => {
    downloadDialog.value = true;
    if(downloadZipProgressValue.value==0||downloadZipProgressValue.value==100){
        downloadZipProgressValue.value = 0;
        axios.get('http://130.216.208.137:8089/download_workflow_outputs/22', {
            responseType: 'blob',
            auth: {
                username: username,
                password: password
            },
            onDownloadProgress: (progressEvent) => {
                const { loaded, total } = progressEvent;
                if (typeof total === 'number') {
                    const percentCompleted = Math.round((loaded * 100) / total);
                    console.log(`Download progress: ${percentCompleted}%`);
                    downloadZipProgressValue.value = percentCompleted
                } else {
                    console.log(`Downloaded ${loaded} bytes (total size unknown)`);
                }
            }
        })
        .then(response => {
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'dataset.zip');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }
    
}

const handleAssayVerifyClicked = async (assay_seek_id:string) => {
    window.open("http://bn363773:8888/lab/tree/20250722_105946/verify.ipynb","_blank")
}

const handleAssayMonitorClicked = async (assay_seek_id:string) => {
    window.open(assayExecute.value![assay_seek_id].url, '_blank');
}

const handleAssayLaunchClicked = async (assay_seek_id:string) => {
    const res = await useDashboardGetAssayLaunch(assay_seek_id);
    if (res.type === "airflow"){
        setAssayExecute(assay_seek_id, "Monitor", res.data);
    }else if (res.type === "gui"){
        if (!!res.data){
            router.push({name: res.data, query: { assayId: assay_seek_id }});
        }
    }else if (res.type === "EP3 workflow launch"){
        window.open(res.data, '_blank')
    }
}

const handleExploreClicked = async (seek_id:string, name:string, category:string, des:string) => {
    const explored = exploredCard.value.find(item => item.category === category);
    if (!explored){
        setExploredCard(category, currentCategoryData.value)
    }else{
        explored.data = currentCategoryData.value;
    }
    detailsRenderItems.value.categories.push({category: category, name: name, description: des});
    detailsRenderItems.value.description = des;

    setBreadCrumbsCategory(category);

    const index = breadCrumbs.findIndex(item => item === category);
    setCurrentCategory(breadCrumbs[index+1]);
    breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });
    
    await getDashboardCategoryChildren(seek_id, category);
    
    // temporary
    if (category == "Programmes"){
        dashboardCategoryChildren.value!.sort((a, b) => a.name.localeCompare(b.name));
    }
    setCurrentCategoryData(dashboardCategoryChildren.value!);
}

watch(()=>currentCategoryData.value, (newVal)=>{
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

// const handleSwitchModel = (val:boolean|null) => {
//     console.log(val);
    
//     setSwitchModel(val as boolean);
//     isSwitchClicked.value = true;
//     if (val){
//         let i = 0;
//         const a:any[] = [];
//         currentCategoryData.value.map(item => {
//             if (val && i>2){
//                 a.push(item);
//             }
//             i +=1;
//         })
//         currentCategoryData.value = a;
//     }else{
//         setCurrentCategoryData(dashboardCategoryChildren.value!);
//     }
// }

onMounted(async () => {

    if (!user.value) router.push({name: 'Login'});
    if (!!studyDetails.value === false) await getTumourStudyDetails();

    const flag = isClinicianView.value;

    if (route.params.dashboardType === "study"){
        setClinicianView(false);
    }else if (route.params.dashboardType === "clinician"){
        setClinicianView(true);
    }


    if (currentCategoryData.value.length === 0 || flag !== isClinicianView.value){
        currentCategoryData.value.length = 0;
        breadCrumbsItems.value = [
            { title: 'Programmes', disabled: false },
        ];
        setCurrentCategory("Programmes");
        exploredCard.value = [];
        detailsRenderItems.value = {
            categories: [],
            description: ""
        };
        await getDashboardProgrammes();
        currentCategoryData.value = dashboardProgrammes.value!.filter((item:IDashboardCategory) => {
            if (isClinicianView.value === false){

                if (item.name !== "Auckland hospital"){
                    return item;
                }
                // return item;
            }else if (isClinicianView.value === true){
                if (item.name === "Auckland hospital"){
                    return item;
                }
            }
        });
    }

   
    // if (currentCategoryData.value.length === 0){
    //     currentCategoryData.value = dashboardProgrammes.value!;
    // }
        
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
.container {
    height: 100vh;
    position: relative;
    background-image: url("@/assets/login_bg.jpg"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px); 
}
.container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: inherit; 
  filter: blur(10px); 
  -webkit-filter: blur(10px); 
  z-index: -1; 
}
.breadcrumbs {
    top: 110px;
    /* border-radius: 5% 95% 97% 3% / 42% 45% 55% 58%  ; */
    border-radius: 10px;
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
    height: 75%;
    margin-top: 150px;
}
.tooltip-panel{
    cursor: help;
}
.custom-switch{
    top: 20%;
    right: 100px;
}

</style>