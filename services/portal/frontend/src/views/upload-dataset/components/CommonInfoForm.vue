<template>
     <h4 class="my-2">Source Url *</h4>
        <v-text-field
            v-model="repository_url"
            :rules="sourceUrlRules"
            label="Git repository URL"
            placeholder="https://github.com/user/repo.git"
            required
            @blur="onBlur"
            :error-messages="(!!cwlRepoErr && !cwlRepoErr.available) ? cwlRepoErr.message : ''"
            clearable
        ></v-text-field>
        <div class="d-flex flex-row">
            <div class="w-100">
                <h4 class="my-2">Workflow Name *</h4>
                <v-text-field
                    v-model="name"
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
                    v-model="author"
                    label="Your Name"
                    clearable
                ></v-text-field>
            </div>
            <div class="w-100">
                <h4 class="my-2">Version</h4>
                <v-text-field
                    v-model="version"
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
                v-model="description"
                placeholder="Brief description of your workflow tool..."
                rows="2"
                counter
                clearable
                ></v-textarea>
        </div>

        <slot></slot>
        <!-- Terms of Service Checkbox -->
        <v-checkbox
            v-model="policy_checkbox"
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
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<
{
    nameErr: { available: boolean; message: string } | undefined | null;
    cwlRepoErr: { available: boolean; message: string } | undefined | null;
}>()

const repository_url = defineModel<string>('repository_url')
const name = defineModel<string>('name')
const author = defineModel<string>('author')
const version = defineModel<string>('version')
const description = defineModel<string>('description')
const policy_checkbox = defineModel<boolean>('policyCheckbox', { default: false })

const emit = defineEmits(["onSoundUrlBlur", "onNameBlur"])
const onBlur = () => {
    emit("onSoundUrlBlur")
}
const onNameBlur = () => {
    emit("onNameBlur")
}

const githubRepoRegex = /^(https:\/\/github\.com\/[\w.-]+\/[\w.-]+)(\.git)?$|^(git@github\.com:[\w.-]+\/[\w.-]+)(\.git)?$/;
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;

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
</script>

<style scoped>

</style>