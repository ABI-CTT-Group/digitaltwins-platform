<template>
    <v-alert
        v-show="showAlert"
        :text="alertText"
        title="Required Fields Missing"
        type="error"
    ></v-alert>
    <div>
        <h3 class="text-cyan">Workflow Tool Information</h3>
        <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
        
        <v-form ref="form" class="px-5">
            <h4 class="my-2">Choose the workflow tool type *</h4>
             <v-radio-group 
                v-model="toolInfomationFormData.label"
                inline
                class="w-100 d-flex justify-start"
                @update:modelValue="handleLabelChange"
                >
                <v-radio color="success" label="Web GUI" value="GUI"></v-radio>
                <v-radio color="success" label="CWL Script" value="Script" class="ml-2"></v-radio>
            </v-radio-group>  

            <CommonInfoForm
                :cwl-repo-err="cwlRepoErr"
                :name-err="nameErr"
                v-model:repository_url="toolInfomationFormData.repository_url"
                v-model:name="toolInfomationFormData.name"
                v-model:author="toolInfomationFormData.author"
                v-model:version="toolInfomationFormData.version"
                v-model:description="toolInfomationFormData.description"
                v-model:policy-checkbox="policyCheckbox"
                @onSoundUrlBlur="onRepoBlur"
                @onNameBlur="onNameBlur"
           >

            <!-- GUI Plugin -->
            <div v-if="toolInfomationFormData.label === 'GUI'" class="w-100">
                <div class="w-100">
                    <h4 class="my-2">has backend? *</h4>
                    <v-radio-group inline v-model="toolInfomationFormData.has_backend" class="w-100 d-flex justify-between">
                        <v-radio label="Yes" :value=true></v-radio>
                        <v-radio label="No" :value=false></v-radio>
                    </v-radio-group>
                </div>
                <div class="w-100 d-flex flex-row">
                    <div v-show="toolInfomationFormData.has_backend" class="w-100 mr-1">
                        <h4 class="my-2">Frontend Folder Name *</h4>
                        <v-select
                            v-model="toolInfomationFormData.frontend_folder"
                            :items="foldersInRootRepo"
                            :rules="frontendFolderRules"
                            label="Frontend Folder"
                        ></v-select>
                    </div>
                    <div class="w-100 ml-1">
                        <h4 class="my-2">Build Command *</h4>
                        <v-text-field
                            v-model="toolInfomationFormData.frontend_build_command"
                            :rules="frontendCommandRules"
                            label="Frontend Build Command"
                            clearable
                            required
                        ></v-text-field>
                    </div>
                </div>
                <div class="w-100 d-flex flex-row">
                    <div v-show="toolInfomationFormData.has_backend" class="w-100 mr-1">
                        <h4 class="mb-2">Backend Folder Name *</h4>
                        <v-select
                            v-model="toolInfomationFormData.backend_folder"
                            :items="foldersInRootRepo"
                            :rules="backendFolderRules"
                            label="Backend Folder"
                        ></v-select>
                    </div>
                    <div v-show="toolInfomationFormData.has_backend" class="w-100 ml-1">
                        <h4 class="mb-2">Deploy Command (fixed) *</h4>
                        <v-text-field
                            v-model="toolInfomationFormData.backend_deploy_command"
                            bg-color="cyan-darken-4"  
                            variant="solo"
                            readonly
                        ></v-text-field>
                    </div>
                </div>
            </div>
            </CommonInfoForm>
        </v-form>
        <v-divider class="mb-5" :thickness="3"></v-divider>
        <div class="d-flex flex-row justify-center">
            <v-btn
                color="red"
                :text="'Cancel'"
                variant="tonal"
                :width="150"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleCancel"
            ></v-btn>
            <v-btn
                color="success"
                :text="'Submit Tool'"
                variant="tonal"
                :width="150"
                rounded="md"
                class="hover-animate ma-5"
                @click="handleSubmit"
            ></v-btn>
        </div>
    </div>
</template>

<script setup lang="ts">
import axios from 'axios'
import { ref, watch, reactive, watchEffect} from 'vue'
import { IToolInformationStep, CheckNameResponse } from '@/models/uiTypes'
import { useCheckPluginName } from '@/plugins/plugin_api'
import CommonInfoForm from '@/views/upload-dataset/components/CommonInfoForm.vue'
import { getRepoNameFromUrl, getRepoAuthorFromUrl, getRepoContents, convertToApiUrl} from '@/views/upload-dataset/components/utils'
import { GitContent } from '@/models/uiTypes'

const emit = defineEmits(["cancel", "submit"])
const form = ref()
const policyCheckbox = ref(false)
const showAlert = ref(false)
const cwlCheck = ref(true);
const alertText = ref("")
const toolInfomationFormData = reactive<IToolInformationStep>({
    label: "GUI",
    repository_url:"",
    name:"",
    author:"",
    version:"0.0.0",
    description:"",
    frontend_folder:"",
    frontend_build_command:"npm run build",
    has_backend:true,
    backend_folder:"",
    backend_deploy_command:"docker compose up --build -d",
    plugin_metadata:{}
})
const nameErr = ref<CheckNameResponse>()
const frontendFolderErr = ref<CheckNameResponse>()
const backendFolderErr = ref<CheckNameResponse>()
const cwlRepoErr = ref<CheckNameResponse>()

const foldersInRootRepo = ref<string[]>([])
const frontendCommandRegex = /^(npm|yarn)\s+\S+/


const frontendFolderRules = ref([
    (v:string) => toolInfomationFormData.has_backend ? !!v || "Make sure the folder name matches the frontend folder in your tool’s GitHub repo" : true
])
const frontendCommandRules = ref([
    (v:string) => !!v || 'Command to build your plugin (e.g., npm run build, yarn build)',
    (v:string) => frontendCommandRegex.test(v) || "At the moment, the server supports only npm or yarn commands"
])
const backendFolderRules = [
    (v: string) => {
        if (!toolInfomationFormData.has_backend) return true
        return !!v || "The backend folder name can’t be empty!"
    }
]

const addGitSuffix = (url:string) => {
  if (!url) return ''
  const cleaned = url.replace(/(\.git)?$/, '')
  return cleaned + '.git'
}

const handleLabelChange = () =>{
    if (toolInfomationFormData.label === "Script"){
        toolInfomationFormData.has_backend = false;
        onRepoBlur();

    }else{
        cwlCheck.value = false;
        cwlRepoErr.value = undefined;
    }
    showAlert.value = false;
}

const onRepoBlur = () => {
    if (!toolInfomationFormData.repository_url) return
    if (!toolInfomationFormData.repository_url.endsWith('.git')) {
        toolInfomationFormData.repository_url = addGitSuffix(toolInfomationFormData.repository_url);
    }
    toolInfomationFormData.name = getRepoNameFromUrl(toolInfomationFormData.repository_url);
    toolInfomationFormData.author = getRepoAuthorFromUrl(toolInfomationFormData.repository_url);
    onNameBlur();

    // Fetch repo contents to get folders in root
    foldersInRootRepo.value = [];
    getRepoContents(toolInfomationFormData.repository_url).then((res)=>{
        const folders = res!.data as GitContent[];
        const cwlFilesInRoot: string[] = [];
        folders.forEach((item: GitContent)=>{
            if (item.type == 'dir'){
                foldersInRootRepo.value.push(item.name)
            }else if(toolInfomationFormData.label === "Script" && item.type == 'file' && item.name.endsWith(".cwl")){
                 cwlFilesInRoot.push(item.name);
            }
        })
        if (toolInfomationFormData.label === "Script"){
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
        }
    }).catch((err) => console.error("Error fetching repo contents:", err));

    findPackageJson(toolInfomationFormData.repository_url).then((files)=>{
        if(files.length > 0){
            const packageJsonPath = files[0];
            getRepoContents(toolInfomationFormData.repository_url, packageJsonPath).then((res)=>{
                const data = res.data;
                const decoded = atob(data.content.replace(/\n/g, ''));
                const packageJson = JSON.parse(decoded)
                toolInfomationFormData.version = packageJson.version;
            }).catch(console.error)
        }
    }).catch(console.error)
}


const onNameBlur = async () => {
    // Don't need to check if name is empty
    nameErr.value = await useCheckPluginName(toolInfomationFormData.name)
}

const handleFrontendFolderBlur = () => {
    if (checkFolderNameInRoot(toolInfomationFormData.frontend_folder)){
        frontendFolderErr.value = {
           available: true,
           message: '' 
        }
    }else{
        frontendFolderErr.value = {
            available: false,
            message: `'${toolInfomationFormData.frontend_folder}' is not in your repo folders: [${foldersInRootRepo.value}]`
        }
    }
}

const handleBackendFolderBlur = () => {
    if (checkFolderNameInRoot(toolInfomationFormData.backend_folder)){
        backendFolderErr.value = {
           available: true,
           message: '' 
        }
    }else{
        backendFolderErr.value = {
            available: false,
            message: `'${toolInfomationFormData.backend_folder}' is not in your repo folders: [${foldersInRootRepo.value}]`
        }
    }
}

async function findPackageJson(url:string) {
    const branch = "main";
    const gitTreeUrl = convertToApiUrl(url) + `/git/trees/${branch}?recursive=1`;

    const res = await fetch(gitTreeUrl, {
        headers: {
        Accept: 'application/vnd.github+json',
        // Authorization: `Bearer ${token}`, // if the github repo is private
        },
    });

    if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);

    const data = await res.json();
    const tree = data.tree;

    const packages = tree.filter((item: any) => item.path.endsWith('package.json'));

    return packages.map((item: any) => item.path);
}

const checkFolderNameInRoot = (name: string) => {
    return foldersInRootRepo.value.includes(name)
}

watch(()=>toolInfomationFormData.has_backend,(newVal, oldVal)=>{
    policyCheckbox.value = false;
})


async function validate(){
    const { valid } = await form.value.validate();
    onNameBlur();
    if(toolInfomationFormData.label === "GUI"){
       
        if (toolInfomationFormData.has_backend){
            handleBackendFolderBlur();
            handleFrontendFolderBlur();
            if( 
                valid && 
                nameErr.value?.available &&
                frontendFolderErr.value?.available &&
                backendFolderErr.value?.available)
            {
                return true;
            }
        }else{
            if( 
                valid && 
                nameErr.value?.available)
            {
                return true;
            }
        }
    }else if(toolInfomationFormData.label === "Script"){
        if (valid && nameErr.value?.available && cwlCheck.value){
            return true;
        }
    }
    return false;
}

async function handleCancel () {  
    emit("cancel")
}

async function handleSubmit() {
    const result = await validate();
    if (result){
        emit("submit", toolInfomationFormData)
        showAlert.value = false
    }else{
        showAlert.value = true
        alertText.value = "Some required fields are missing. Please provide your GitHub repository, workflow tool name, build command, and, if the tool includes a backend, fill in the frontend and backend folder details."
    }
    
}

</script>

<style scoped>

</style>