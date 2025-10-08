<template>
    <div class="container d-flex flex-column align-center">
        <div class="position-fixed breadcrumbs d-flex justify-start align-center w-66">
            <v-breadcrumbs
                class="custom-pointer font-weight-black"
                :items="breadCrumbsItems"
                divider="/"
                @click="handleBreadCrumbsClick"
            ></v-breadcrumbs>
        </div>
        <!-- <div class="position-fixed dashboard-title fancy-title">
            {{ isClinicianView ? "Clinician Dashboard" : "Study Dashboard" }}
        </div> -->
        <div>
            <HelpIcon class="position-fixed dashboard-title" :size="50" @click="hanleHelpClick"/>
        </div>
        <v-card v-if="currentCategory !== 'Programmes' && currentCategory !== ''" class="position-fixed intro d-flex flex-column overflow-y-auto justify-space-around pa-5" color="transparent">
            <v-card-text>
                <div v-for="c in detailsRenderItems.categories" :key="c.name" class="text-grey-lighten-3 my-2 d-flex flex-row align-center">
                    <span  class="tooltip-title d-flex justify-center">
                        <v-icon
                            color="blue-darken-1"
                            icon="mdi-information-outline"
                            class="mx-1"
                            size="small"
                            ></v-icon>
                        <v-tooltip
                            activator="parent"
                            location="bottom"
                            max-width="300"
                        >
                            {{ c.description }}
                        </v-tooltip>
                        {{ c.category === 'Studies' ? 'Study' : c.category.slice(0,-1) }} 
                    </span>
                    <span class="tooltip-panel mx-3">
                        {{c.name}} 
                    </span>
                </div>
            </v-card-text>
        </v-card>

        <div  class="basic-card-container w-100 d-flex flex-column justify-center align-center ">
            <div class="w-75 d-flex flex-wrap px-6 mt-10 justify-center align-center overflow-y-auto">
                <AssayBasicCard v-for="data in currentCategoryData" 
                            :key="data.name" 
                            :data="data"
                            @expand-clicked="handleAssayExpandClicked"
                            @explore-clicked="handleExploreClicked"
                            @assay-edit-clicked="handleAssayEditClicked"
                            @assay-save="handleAssaySave"
                            @assay-launch-clicked="handleAssayLaunchClicked"
                            @assay-monitor-clicked="handleAssayMonitorClicked"
                            @assay-verify-clicked="handleAssayVerifyClicked"
                            @assay-download-clicked="handleAssayDownloadClicked"
                            @assay-upload-clicked="handleAssayUploadClicked">
                </AssayBasicCard>
            </div>
        </div>
        <DownloadSheet :download-zip-progress-value="downloadZipProgressValue" v-model:download-dialog="downloadDialog"></DownloadSheet>
        <SubmitSheet v-model:submit-dialog="submitDialog" :submit-state="submitState" />
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useUser } from "@/plugins/hooks/user";
import { storeToRefs } from "pinia";
import { useDashboardPageStore } from '@/store/states';
import { useDashboardGetAssayDetails, useDashboardGetAssayLaunch } from "@/plugins/dashboard_api";
import { useDashboardProgrammesStore, useDashboardCategoryChildrenStore, useDashboardSaveAssayDetailsStore } from '@/store/dashboard_store';
import {IDashboardCategory, IAssayDetails} from "@/models/apiTypes";
import AssayBasicCard from '@/components/dt-components/AssayBasicCard.vue';
import axios from 'axios';
import DownloadSheet from '@/components/dt-components/DownloadSheet.vue';
import SubmitSheet from '@/components/dt-components/SubmitSheet.vue';
import { reWriteCategoryDetails } from './utils';
import HelpIcon from '@/components/commonBar/HelpIcon.vue';

const username = 'admin';
const password = 'ctt_digitaltwins_0';


const router = useRouter();
const route = useRoute();

const { user } = useUser();
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

const breadCrumbs = ["Programmes", "Projects", "Investigations", "Studies", "Assays"];
// const isSwitchClicked = ref(false);

const downloadZipProgressValue = ref(0);
const downloadDialog = ref(false);
const submitDialog = ref(false);
const submitState = ref("waiting");

const handleBreadCrumbsClick = (res:PointerEvent) => {
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
    submitDialog.value = true
    submitState.value = "waiting"
     axios.get('http://130.216.208.137:8089/upload_workflow_outputs/22', {
        auth: {
            username: username,
            password: password
        }
        })
        .then(response => {
            submitState.value = String(response.data) 
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
    };
    
}

const handleAssayVerifyClicked = async (assay_seek_id:string) => {
    const assayDetails = allAssayDetailsOfStudy.value[assay_seek_id];
    const workflowUUID = assayDetails.workflow.uuid;
    console.log(assayDetails);
    
    console.log("ddaas");
    
    console.log(workflowUUID);
    
    window.open(`http://130.216.216.26:8008/lab/tree/workflow_outputs/${workflowUUID}/verify.ipynb`,"_blank");
    // window.open("http://bn363773:8888/lab/tree/20250722_105946/verify.ipynb","_blank");
}

const handleAssayMonitorClicked = async (assay_seek_id:string) => {
    window.open(assayExecute.value![assay_seek_id].url, '_blank');
}

const handleAssayLaunchClicked = async (assay_seek_id:string) => {
    setCurrentAssayDetails(allAssayDetailsOfStudy.value[assay_seek_id])
    const res = await useDashboardGetAssayLaunch(assay_seek_id);
    if (res.type === "airflow"){
        setAssayExecute(assay_seek_id, "Monitor", res.data);
    }else if (res.type === "gui"){
        // if (!!res.data){
        //     router.push({name: "PluginRegister", query: { assayId: assay_seek_id }});
        // }
    }else if (res.type === "EP3 workflow launch"){
        window.open(res.data, '_blank')
    }
}

const handleAssayExpandClicked = (assay_seek_id:string, name:string) => {
    console.log(name);
    console.log("dadaasd");
    
    router.push({name: "LaunchedAssayOverview", query: { assayId: assay_seek_id }});
}

const handleExploreClicked = async (seek_id:string, name:string, category:string, des:string) => {
    const explored = exploredCard.value.find(item => item.category === category);
    if (!explored){
        setExploredCard(category, currentCategoryData.value)
    }else{
        explored.data = currentCategoryData.value;
    }
    detailsRenderItems.value.categories.push({category: category, name: name, description: reWriteCategoryDetails(category)});
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

const hanleHelpClick = () => {
    window.open("https://github.com/ABI-CTT-Group/DigitalTWINS-Portal?tab=readme-ov-file#how-to-use-the-study-dashboard", "_blank");
}


onMounted(async () => {

    if (!user.value) router.push({name: 'Login'});

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
        
})

</script>

<style scoped>
.breadcrumbs {
    top: 110px;
    /* border-radius: 5% 95% 97% 3% / 42% 45% 55% 58%  ; */
    border-radius: 10px;
    /* box-shadow:  6px 6px 20px  #636363,
                -6px -6px 20px #878787; */
    box-shadow:  6px 6px 20px  #0e3f5a,
                -6px -6px 20px #0b2433;
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
    height: 95dvh;
    padding-top: 150px;
}
.tooltip-title{
     cursor: help;
    font-weight: 800;   
    color: coral;
}
.tooltip-panel{
   
    font-size: 0.8rem;
    line-height: 1.2;
}
.custom-switch{
    top: 20%;
    right: 100px;
}
.dialog-title{
    font-size: 1.8rem;
    font-weight: 800;
}
.dialog-title-name{
    font-size: 1.1rem;
    font-weight: 400;
}
.dialog-description{
    font-size: 0.9rem;
    line-height: 1.5;
    color: #b0bec5;
}
.dashboard-title{
    top: 100px;
    right: 35px;
    max-width: 10dvw;
}

</style>