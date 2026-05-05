<template>
    <h4 class="my-2">Source *</h4>
    <v-radio-group
        v-model="sourceType"
        inline
        class="w-100 d-flex justify-start mb-1"
        hide-details
    >
        <v-radio color="success" label="GitHub URL" value="github" />
        <v-radio color="success" label="Local Folder" value="local" class="ml-2" />
    </v-radio-group>

    <template v-if="sourceType === 'github'">
        <h4 class="my-2">Source Url *</h4>
        <v-text-field
            v-model="repositoryUrl"
            :rules="sourceUrlRules"
            label="Git repository URL"
            placeholder="https://github.com/user/repo.git"
            required
            @blur="onBlur"
            :error-messages="(!!cwlRepoErr && !cwlRepoErr.available) ? cwlRepoErr.message : ''"
            clearable
        ></v-text-field>
    </template>
    <template v-else>
        <h4 class="my-2">Source Folder *</h4>
        <slot name="dropzone"></slot>
        <div
            v-if="!!cwlRepoErr && !cwlRepoErr.available"
            class="text-error text-caption ml-1 mt-1"
        >{{ cwlRepoErr.message }}</div>
    </template>
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
                    :readonly="sourceType === 'github'"
                    :bg-color="sourceType === 'github' ? 'cyan-darken-4' : undefined"
                    :variant="sourceType === 'github' ? 'solo' : 'filled'"
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
import { computed } from 'vue'
import type { SourceType } from '@/models/types'

defineProps<
{
    nameErr: { available: boolean; message: string } | undefined | null;
    cwlRepoErr: { available: boolean; message: string } | undefined | null;
}>()

const repositoryUrl = defineModel<string>('repositoryUrl')
const name = defineModel<string>('name')
const author = defineModel<string>('author')
const version = defineModel<string>('version')
const description = defineModel<string>('description')
const policy_checkbox = defineModel<boolean>('policyCheckbox', { default: false })
const sourceType = defineModel<SourceType>('sourceType', { default: 'github' })

const emit = defineEmits(["onSoundUrlBlur", "onNameBlur"])
const onBlur = () => {
    emit("onSoundUrlBlur")
}
const onNameBlur = () => {
    emit("onNameBlur")
}

const githubRepoRegex = /^(https:\/\/github\.com\/[\w.-]+\/[\w.-]+)(\.git)?$|^(git@github\.com:[\w.-]+\/[\w.-]+)(\.git)?$/;
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;

// URL rules only run when source is GitHub; in local mode these are bypassed.
const sourceUrlRules = computed(() => {
    if (sourceType.value !== 'github') return [];
    return [
        (v: string) => !!v || 'Source URL is required',
        (v: string) => githubRepoRegex.test(v) || 'Must be a valid GitHub repository URL',
    ];
})
const pluginNameRules = [
    (v:string) => !!v || 'Workflow tool name is required',
]
const versionRules = [
    (v:string) => !!v || 'Version is required',
    (v:string) => semverRegex.test(v) || 'Version should be semantic versioning (e.g., 1.0.0)'
]
</script>

<style scoped>

</style>
