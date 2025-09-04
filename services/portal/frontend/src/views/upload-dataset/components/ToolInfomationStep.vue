<template>
    <div>
        <h3 class="text-cyan">Workflow Tool Information</h3>
        <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
        
        <v-form ref="form" class="px-5">
            <h4 class="my-2">Source Url *</h4>
            <v-text-field
                v-model="toolInfomationFormData.sourceUrl"
                :rules="sourceUrlRules"
                label="Git repository URL"
                placeholder="https://github.com/user/repo.git"
                required
                @blur="onBlur"
                clearable
            ></v-text-field>
            <div class="d-flex flex-row">
                <div class="w-100">
                    <h4 class="my-2">Plugin Name</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.pluginName"
                        label="My Workflow Tool"
                        clearable
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
                    <h4 class="my-2">Version *</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.version"
                        :rules="versionRules"
                        label="Version"
                        placeholder="Semantic versioning (e.g., 1.0.0)"
                        required
                        clearable
                    ></v-text-field>
                </div>
            </div>
            <div class="w-100">
                <h4 class="my-2">Description</h4>
                <v-textarea
                    :model-value="toolInfomationFormData.description"
                    placeholder="Brief description of your workflow tool..."
                    rows="2"
                    counter
                    clearable
                    ></v-textarea>
            </div>
            <div class="w-100 d-flex flex-row">
                <div class="w-100 mr-1">
                    <h4 class="my-2">Frontend Folder Name *</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.frontendFolderName"
                        :rules="frontendFolderRules"
                        label="Frontend Folder"
                        :error-messages="''"
                        clearable
                        required
                    ></v-text-field>
                </div>
                <div class="w-100 ml-1">
                    <h4 class="my-2">Build Command *</h4>
                    <v-text-field
                        v-model="toolInfomationFormData.frontendBuildCommand"
                        :rules="frontendCommandRules"
                        label="Frontend Build Command"
                        clearable
                        required
                    ></v-text-field>
                </div>
            </div>
            <div class="w-100 d-flex flex-column">
                <h4 class="my-2">has backend? *</h4>
                <v-radio-group inline v-model="toolInfomationFormData.hasbackend">
                    <v-radio label="Yes" :value=true></v-radio>
                    <v-radio label="No" :value=false></v-radio>
                </v-radio-group>
                <div class="w-100 d-flex flex-row">
                    <div class="w-100 mr-1">
                        <h4 class="mb-2">Backend Folder Name *</h4>
                        <v-text-field
                            v-model="toolInfomationFormData.backendFolderName"
                            :rules="backendFolderRules"
                            label="Backend Folder"
                            :error-messages="''"
                            clearable
                            required
                            :disabled="!toolInfomationFormData.hasbackend"
                        ></v-text-field>
                    </div>
                    <div class="w-100 ml-1">
                        <h4 class="mb-2">Build Command (fixed) *</h4>
                        <v-text-field
                            bg-color="cyan-darken-4"  
                            variant="solo"
                            v-model="toolInfomationFormData.backendBuildCommand"
                            readonly
                            :disabled="!toolInfomationFormData.hasbackend"
                        ></v-text-field>
                    </div>
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
                :disabled="submitBtnDisabled"
                class="hover-animate ma-5"
                @click="handleSubmit"
            ></v-btn>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch, reactive} from 'vue'
import { debounce } from "lodash"
import { IToolInformationStep } from '@/models/uiTypes'


const emit = defineEmits(["cancel", "submit"])
const form = ref()
const policyCheckbox = ref(false)
const submitBtnDisabled = ref(true)
const toolInfomationFormData = reactive<IToolInformationStep>({
    sourceUrl:"",
    pluginName:"",
    author:"",
    version:"1.0.0",
    description:"",
    frontendFolderName:"frontend",
    frontendBuildCommand:"npm run build",
    hasbackend:true,
    backendFolderName:"backend",
    backendBuildCommand:"docker compose up --build -d"
})
const githubRepoRegex = /^(https:\/\/github\.com\/[\w.-]+\/[\w.-]+)(\.git)?$|^(git@github\.com:[\w.-]+\/[\w.-]+)(\.git)?$/;
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;
const frontendCommandRegex = /^(npm|yarn)\s+\S+/

const sourceUrlRules = ref([
    (v:string) => !!v || 'Source URL is required',
    (v:string)  => githubRepoRegex.test(v) || 'Must be a valid GitHub repository URL',
])
const versionRules = ref([
    (v:string) => !!v || 'Version is required',
    (v:string) => semverRegex.test(v) || 'Version should be semantic versioning (e.g., 1.0.0)'
])
const frontendFolderRules = ref([
    (v:string) => !!v || "Make sure the folder name matches the frontend folder in your tool’s GitHub repo"
])
const frontendCommandRules = ref([
    (v:string) => !!v || 'Command to build your plugin (e.g., npm run build, yarn build)',
    (v:string) => frontendCommandRegex.test(v) || "At the moment, the server supports only npm or yarn commands"
])
const backendFolderRules = [
    (v: string) => {
        if (!toolInfomationFormData.hasbackend) return true
        return !!v || "The backend folder name can’t be empty!"
    }
]

const addGitSuffix = (url:string) => {
  if (!url) return ''
  const cleaned = url.replace(/(\.git)?$/, '')
  return cleaned + '.git'
}

const onBlur = () => {
  if (!toolInfomationFormData.sourceUrl) return
  if (!toolInfomationFormData.sourceUrl.endsWith('.git')) {
    toolInfomationFormData.sourceUrl = addGitSuffix(toolInfomationFormData.sourceUrl)
  }
}

watch(()=>toolInfomationFormData.hasbackend,(newVal, oldVal)=>{
    toolInfomationFormData.backendFolderName = newVal ? "backend" : ""
})

watch(policyCheckbox, debounce(async () => {
  const { valid } = await form.value.validate();
  submitBtnDisabled.value = !valid;
  if(!valid) policyCheckbox.value = false;
}, 200))

async function handleCancel () {
    const { valid } = await form.value.validate()
    if (valid) alert('Form is valid')   

    emit("cancel")
}

async function handleSubmit() {
    emit("submit", toolInfomationFormData)
}

</script>

<style scoped>

</style>