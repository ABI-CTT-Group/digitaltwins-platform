<template>
    <v-alert
        v-show="showAlert"
        text="Some required fields are missing. Please provide your GitHub repository, workflow tool name, build command, and, if the tool includes a backend, fill in the frontend and backend folder details."
        title="Required Fields Missing"
        type="error"
    ></v-alert>
    <div>
        <h3 class="text-cyan">Workflow Tool Information</h3>
        <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
        
        <v-form ref="form" class="px-5">
            <h4 class="my-2">Source Url *</h4>
            <v-text-field
                v-model="toolInfomationFormData.repository_url"
                :rules="sourceUrlRules"
                label="Git repository URL"
                placeholder="https://github.com/user/repo.git"
                required
                @blur="onBlur"
                clearable
            ></v-text-field>
            <div class="d-flex flex-row">
                <div class="w-100">
                    <h4 class="my-2">Plugin Name *</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.name"
                        label="My Workflow Tool Name"
                        clearable
                        @blur="onNameBlur"
                        :rules="pluginNameRules"
                        required
                        :error-messages="(!!nameErr && !nameErr.available) ? nameErr.message : ''"
                    ></v-text-field>
                </div>
                <div class="w-100 mx-3" >
                    <h4 class="my-2">Author</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.author"
                        label="Your Name"
                        clearable
                    ></v-text-field>
                </div>
                <div class="w-100">
                    <h4 class="my-2">Version</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.version"
                        :rules="versionRules"
                        required
                        bg-color="cyan-darken-4"  
                        variant="solo"
                        readonly
                    ></v-text-field>
                </div>
            </div>
            <div class="w-100">
                <h4 class="my-2">Description</h4>
                <v-textarea
                    v-model="toolInfomationFormData.description"
                    placeholder="Brief description of your workflow tool..."
                    rows="2"
                    counter
                    clearable
                    ></v-textarea>
            </div>
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
                    <v-text-field
                        v-model="toolInfomationFormData.frontend_folder"
                        :rules="frontendFolderRules"
                        label="Frontend Folder"
                        @blur="handleFrontendFolderBlur"
                        :error-messages="(!!frontendFolderErr && !frontendFolderErr.available) ? frontendFolderErr.message : ''"
                        clearable
                        required
                    ></v-text-field>
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
                    <v-text-field
                        v-model="toolInfomationFormData.backend_folder"
                        :rules="backendFolderRules"
                        label="Backend Folder"
                        @blur="handleBackendFolderBlur"
                        :error-messages="(!!backendFolderErr && !backendFolderErr.available) ? backendFolderErr.message : ''"
                        clearable
                        required
                    ></v-text-field>
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
             <v-checkbox
                    v-model="policyCheckbox"
                    :rules="[v => !!v || 'You must agree to continue!']"
                    required
            >
                <template v-slot:label>
                    I agree to the&nbsp;
                    <a
                        href="#"
                        @click.stop.prevent=""
                    >Terms of Service</a>
                    &nbsp;and&nbsp;
                    <a
                        href="#"
                        @click.stop.prevent=""
                    >Privacy Policy</a>*
                </template>
            </v-checkbox>
            
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
import { debounce } from "lodash"
import { IToolInformationStep, CheckNameResponse } from '@/models/uiTypes'
import { useCheckPluginName } from '@/plugins/plugin_api'

interface GitContent {
    name: string;
    path:string;
    download_url:string;
    git_url:string;
    html_url:string;
    sha:string;
    size:number;
    type:string;
    url:string;
    _links: {
        git:string;
        html:string;
        self:string;
    }
}

const emit = defineEmits(["cancel", "submit"])
const form = ref()
const policyCheckbox = ref(false)
const showAlert = ref(false)
const toolInfomationFormData = reactive<IToolInformationStep>({
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
const foldersInRootRepo = ref<string[]>([])
const githubRepoRegex = /^(https:\/\/github\.com\/[\w.-]+\/[\w.-]+)(\.git)?$|^(git@github\.com:[\w.-]+\/[\w.-]+)(\.git)?$/;
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;
const frontendCommandRegex = /^(npm|yarn)\s+\S+/

const sourceUrlRules = ref([
    (v:string) => !!v || 'Source URL is required',
    (v:string)  => githubRepoRegex.test(v) || 'Must be a valid GitHub repository URL',
])
const pluginNameRules = ref([
    (v:string) => !!v || 'Workflow tool name is required',
])
const versionRules = ref([
    (v:string) => !!v || 'Version is required',
    (v:string) => semverRegex.test(v) || 'Version should be semantic versioning (e.g., 1.0.0)'
])
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

const onBlur = () => {
  if (!toolInfomationFormData.repository_url) return
  if (!toolInfomationFormData.repository_url.endsWith('.git')) {
    toolInfomationFormData.repository_url = addGitSuffix(toolInfomationFormData.repository_url);
    getRepoContents(toolInfomationFormData.repository_url).then((res)=>{
        const folders = res!.data as GitContent[];
        folders.forEach((item: GitContent)=>{
            if (item.type == 'dir'){
                foldersInRootRepo.value.push(item.name)
            }
        })
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
}

const onNameBlur = async () => {
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

function convertToApiUrl(repoUrl:string) {
        repoUrl = repoUrl.replace(/\.git$/, "").replace(/\/$/, "");

        const parts = repoUrl.split("/");
        const owner = parts[parts.length - 2];
        const repo = parts[parts.length - 1];

        return `https://api.github.com/repos/${owner}/${repo}`;
    }

const getRepoContents = async (url:string, path:string ="") => {
    foldersInRootRepo.value = [];
    const rootContentUrl = convertToApiUrl(url) + `/contents/${path}`;
    const res = await axios.get(rootContentUrl);
    return res
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
    }
    
}

</script>

<style scoped>

</style>