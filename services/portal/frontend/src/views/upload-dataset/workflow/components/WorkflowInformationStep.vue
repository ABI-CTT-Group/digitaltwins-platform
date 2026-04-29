<template>
    <v-alert
        v-show="showAlert"
        text="Some required fields are missing. Please provide your GitHub repository, workflow name, and annotating information."
        title="Required Fields Missing"
        type="error"
    ></v-alert>
    <div>
        <h3 class="text-cyan">Workflow Information</h3>
        <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
        
        <v-form ref="form" class="px-5">
            
           <CommonInfoForm
            :cwl-repo-err="cwlRepoErr"
            :name-err="nameErr"
            v-model:repository_url="workflowFormData.repository_url"
            v-model:name="workflowFormData.name"
            v-model:author="workflowFormData.author"
            v-model:version="workflowFormData.version"
            v-model:description="workflowFormData.description"
            v-model:policy-checkbox="policyCheckbox"
            @onSoundUrlBlur="onRepoBlur"
            @onNameBlur="onNameBlur"
           >
           </CommonInfoForm>
        </v-form>
        <v-divider class="mb-5" :thickness="3"></v-divider>
        <div class="d-flex flex-row justify-center">
            <v-btn
                color="red"
                :text="'Cancel'"
                variant="tonal"
                :width="200"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleCancel"
            ></v-btn>
            <v-btn
                color="success"
                :text="'Submit Workflow'"
                variant="tonal"
                :width="200"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleSubmit"
            ></v-btn>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch, reactive, watchEffect} from 'vue'
import CommonInfoForm from '@/views/upload-dataset/components/CommonInfoForm.vue'
import { IToolInformationStep, CheckNameResponse, IWorkflowInformationStep } from '@/models/uiTypes'
import { useCheckPluginName } from '@/plugins/workflow_api'
import { getRepoNameFromUrl, getRepoAuthorFromUrl, getRepoContents} from '@/views/upload-dataset/components/utils'
import { GitContent } from '@/models/uiTypes'



const emit = defineEmits(["cancel", "submit"])
const form = ref()
const policyCheckbox = ref(false)
const showAlert = ref(false)
const workflowFormData = reactive<IWorkflowInformationStep>({
    repository_url:"",
    name:"",
    author:"",
    version:"0.0.0",
    description:"",
})
const cwlCheck = ref(false);
const nameErr = ref<CheckNameResponse>()
const cwlRepoErr = ref<CheckNameResponse>()


const addGitSuffix = (url:string) => {
  if (!url) return ''
  const cleaned = url.replace(/(\.git)?$/, '')
  return cleaned + '.git'
}


const onRepoBlur = () => {
    if (!workflowFormData.repository_url) return
    if (!workflowFormData.repository_url.endsWith('.git')) {
        workflowFormData.repository_url = addGitSuffix(workflowFormData.repository_url);
    }
    workflowFormData.name = getRepoNameFromUrl(workflowFormData.repository_url);
    workflowFormData.author = getRepoAuthorFromUrl(workflowFormData.repository_url);
    onNameBlur();

    // Fetch repo contents to get folders in root
    getRepoContents(workflowFormData.repository_url).then((res)=>{
        const folders = res!.data as GitContent[];
        const cwlFilesInRoot: string[] = [];
        folders.forEach((item: GitContent)=>{
           if(item.type == 'file' && item.name.endsWith(".cwl")){
                 cwlFilesInRoot.push(item.name);
            }
        })
        if (cwlFilesInRoot.length > 0){
            cwlCheck.value = true;
            cwlRepoErr.value = {
                available: true,
                message: ''
            }
        }else{
            cwlCheck.value = false;
            cwlRepoErr.value = {
                available: false,
                message: "No CWL files found in the root of the repository."
            }
        }
    }).catch((err) => console.error("Error fetching repo contents:", err));
}



const onNameBlur = async () => {
    // Don't need to check if name is empty
    nameErr.value = await useCheckPluginName(workflowFormData.name)
}


async function validate(){
    const { valid } = await form.value.validate();
    // onNameBlur();
    // if (valid && nameErr.value?.available && cwlCheck.value){
    //     return true;
    // }

    if (valid && cwlCheck.value){
        return true;
    }
    return false;
}

async function handleCancel () {  
    emit("cancel")
}

async function handleSubmit() {
    const result = await validate();
    if (result){
        emit("submit", workflowFormData)
        showAlert.value = false
    }else{
        showAlert.value = true
    }
}

</script>

<style scoped>

</style>