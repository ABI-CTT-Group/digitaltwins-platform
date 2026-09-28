<template>
    <h4 class="my-2">Source *</h4>
    <v-radio-group
        v-model="sourceMode"
        inline
        class="w-100 d-flex justify-start mb-1"
        hide-details
    >
        <v-radio color="#5fd6e8" label="Git URL" value="git" />
        <v-radio color="#5fd6e8" label="Local Folder" value="local" class="ml-2" />
    </v-radio-group>

    <template v-if="sourceMode === 'git'">
        <div class="d-flex align-center my-2">
            <h4 class="mr-3 mb-0">Source Url *</h4>
            <v-chip
                v-if="repositoryUrl"
                size="x-small"
                color="#5fd6e8"
                variant="tonal"
                prepend-icon="mdi-source-branch"
            >
                {{ providerLabel }}
            </v-chip>
        </div>
        <v-text-field
            v-model="repositoryUrl"
            :rules="sourceUrlRules"
            label="Git repository URL"
            placeholder="https://{github|gitlab|bitbucket}.com/owner/repo.git or https://git.internal.example.com/..."
            required
            @blur="onBlur"
            :error-messages="(!!cwlRepoErr && !cwlRepoErr.available) ? cwlRepoErr.message : ''"
            clearable
        ></v-text-field>

        <!-- Probe failure surface — structured reason drives v-if expansion below.
             No `density="compact"` here because it collapses padding and the icon
             would overlap the message text. -->
        <v-alert
            v-if="probeFailure"
            :type="probeAlertType"
            :icon="probeAlertIcon"
            variant="tonal"
            class="mb-3"
        >
            {{ probeFailure.message }}
        </v-alert>

        <!-- Auth section — grouped in a card so the related fields visually
             cohere. v-if (not v-show) so token never sits in DOM unused.
             watch(repositoryUrl) clears all fields when URL changes. -->
        <v-card
            v-if="showTokenField || showSslToggle"
            variant="outlined"
            class="mb-4 pa-4 auth-card"
        >
            <div class="d-flex align-center mb-3">
                <v-icon icon="mdi-lock-outline" size="small" class="mr-2" />
                <span class="text-subtitle-2">Repository access</span>
            </div>

            <template v-if="showTokenField">
                <v-text-field
                    v-model="token"
                    :type="showTokenPlain ? 'text' : 'password'"
                    :append-inner-icon="showTokenPlain ? 'mdi-eye-off' : 'mdi-eye'"
                    @click:append-inner="showTokenPlain = !showTokenPlain"
                    label="Personal Access Token"
                    placeholder="ghp_... / glpat-... / Bitbucket app password"
                    hint="Used once for this build, then discarded. Rebuild prompts you again."
                    persistent-hint
                    prepend-inner-icon="mdi-key-variant"
                    clearable
                    density="comfortable"
                    @blur="onTokenBlur"
                ></v-text-field>

                <!-- Generic-git only: username has no canonical convention -->
                <v-text-field
                    v-if="sourceType === 'git_generic'"
                    v-model="authUsername"
                    label="Username"
                    placeholder="HTTP basic-auth username your git server expects"
                    hint="Required for self-hosted git when token auth is used"
                    persistent-hint
                    prepend-inner-icon="mdi-account-outline"
                    clearable
                    density="comfortable"
                    class="mt-3"
                    @blur="onTokenBlur"
                ></v-text-field>
            </template>

            <!-- TLS trust checkbox — opens on `tls_error` reason. Visually
                 dangerous because GIT_SSL_NO_VERIFY exposes any token to MITM. -->
            <v-checkbox
                v-if="showSslToggle"
                v-model="trustSelfSigned"
                hide-details
                density="compact"
                class="mt-2"
                @update:model-value="onTokenBlur"
            >
                <template #label>
                    <span class="text-caption">
                        Trust self-signed cert
                        <span class="text-error font-weight-bold ml-2">
                            <v-icon icon="mdi-alert" size="x-small" /> MITM risk — only for trusted internal networks
                        </span>
                    </span>
                </template>
            </v-checkbox>
        </v-card>
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
                    :readonly="sourceMode === 'git'"
                    :variant="sourceMode === 'git' ? 'solo-filled' : 'filled'"
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
import { computed, ref, watch } from 'vue'
import type { SourceType, SourceMode, ProbeFailureReason } from '@/models/types'
import { inferProviderFromUrl, looksLikeGitUrl } from './utils'

const props = defineProps<{
    nameErr: { available: boolean; message: string } | undefined | null;
    cwlRepoErr: { available: boolean; message: string } | undefined | null;
    /** Structured probe failure from the parent's last `gitRepo.refresh()`.
     *  `reason` drives which auxiliary field opens via v-if. */
    probeFailure?: { reason: ProbeFailureReason; message: string } | undefined;
}>()

const repositoryUrl = defineModel<string>('repositoryUrl')
const name = defineModel<string>('name')
const author = defineModel<string>('author')
const version = defineModel<string>('version')
const description = defineModel<string>('description')
const policy_checkbox = defineModel<boolean>('policyCheckbox', { default: false })
const sourceType = defineModel<SourceType>('sourceType', { default: 'github' })

// Transient auth — bound to parent's formData (NOT in PluginCreate payload).
// Parent passes these into useWorkflowToolBuild / useWorkflowBuild as the
// POST body for the first build, then drops them.
const token = defineModel<string>('token', { default: '' })
const authUsername = defineModel<string>('authUsername', { default: '' })
const trustSelfSigned = defineModel<boolean>('trustSelfSigned', { default: false })

const emit = defineEmits(["onSoundUrlBlur", "onNameBlur"])
const onBlur = () => { emit("onSoundUrlBlur") }
const onTokenBlur = () => { emit("onSoundUrlBlur") }
const onNameBlur = () => { emit("onNameBlur") }

const showTokenPlain = ref(false)

// UI toggle (`git` / `local`) derived from sourceType — selecting `local`
// writes the literal 'local'; selecting `git` resets sourceType to
// 'github' as a placeholder, then the URL-blur watch re-infers it.
const sourceMode = computed<SourceMode>({
    get: () => sourceType.value === 'local' ? 'local' : 'git',
    set: (m) => {
        if (m === 'local') sourceType.value = 'local'
        else if (sourceType.value === 'local') sourceType.value = 'github'
    },
})

// Field expansion is computed directly off the probe failure reason so
// reactivity is rock-solid — earlier ref+watch approach raced against the
// URL-change watcher (parent re-assigns formData.repositoryUrl after refresh,
// triggering the URL watcher which resets state) and `showTokenField`
// flickered false right after we'd set it true.
//
// Sticky bit `_tokenLatch` keeps the field visible after the user fills
// their token and probe re-succeeds (probeFailure → undefined). Reset on
// URL change so a fresh URL starts clean.
const _tokenLatch = ref(false)
const _sslLatch = ref(false)

// `auth_required` / `not_found` / `rate_limit` all expand the token field —
// 404 because providers hide unauthorized access behind it (private repos),
// 401 the obvious case, 403/rate_limit because authenticated GitHub API
// has 5000/hr quota vs 60/hr for anonymous.
const showTokenField = computed<boolean>(() => {
    if (_tokenLatch.value) return true
    const pf = props.probeFailure
    return !!(pf && (pf.reason === 'auth_required' || pf.reason === 'not_found' || pf.reason === 'rate_limit'))
})

const showSslToggle = computed<boolean>(() => {
    if (_sslLatch.value) return true
    return props.probeFailure?.reason === 'tls_error'
})

// Once shown, latch — so the field stays visible after probe re-success.
watch(showTokenField, (v) => { if (v) _tokenLatch.value = true })
watch(showSslToggle, (v) => { if (v) _sslLatch.value = true })

// Visual styling for the probe-failure v-alert.
const probeAlertType = computed<'warning' | 'error' | 'info'>(() => {
    if (!props.probeFailure) return 'info'
    switch (props.probeFailure.reason) {
        case 'auth_required':
        case 'not_found':
        case 'rate_limit':
            return 'warning'  // user can fix by adding a token
        case 'tls_error':
            return 'warning'
        case 'network':
        case 'unknown':
            return 'error'
        default:
            return 'info'
    }
})
const probeAlertIcon = computed<string>(() => {
    if (!props.probeFailure) return 'mdi-information'
    switch (props.probeFailure.reason) {
        case 'auth_required':
        case 'not_found':
            // `mdi-lock-outline` (clean lock) instead of `mdi-lock-alert`
            // — the latter has a red badge dot that reads like punctuation
            // sitting next to the message text.
            return 'mdi-lock-outline'
        case 'rate_limit':
            return 'mdi-timer-sand'
        case 'tls_error':
            return 'mdi-shield-outline'
        case 'network':
            return 'mdi-wifi-off'
        default:
            return 'mdi-alert-circle-outline'
    }
})

// On URL change, clear all transient auth state — prevents a stale token
// from a previous URL leaking into the new probe / build. Resets the
// sticky latches too so the new URL gets to re-evaluate from scratch.
watch(repositoryUrl, (url) => {
    token.value = ''
    authUsername.value = ''
    trustSelfSigned.value = false
    _tokenLatch.value = false
    _sslLatch.value = false
    showTokenPlain.value = false
    if (sourceMode.value === 'local') return
    sourceType.value = url ? inferProviderFromUrl(url) : 'github'
})

watch(sourceMode, (m) => {
    if (m === 'local') {
        token.value = ''
        authUsername.value = ''
        trustSelfSigned.value = false
        _tokenLatch.value = false
        _sslLatch.value = false
    }
})

const providerLabel = computed(() => {
    switch (sourceType.value) {
        case 'github': return 'GitHub'
        case 'gitlab': return 'GitLab'
        case 'bitbucket': return 'Bitbucket'
        case 'git_generic': return 'Self-hosted / Generic Git'
        default: return ''
    }
})

// Accept any URL that looks like a git URL (https://... or git@host:...).
// Provider-specific validation happens server-side via probe-source.
const sourceUrlRules = computed(() => {
    if (sourceMode.value !== 'git') return []
    return [
        (v: string) => !!v || 'Source URL is required',
        (v: string) => looksLikeGitUrl(v) || 'Must be a valid git repository URL (https or git@)',
    ]
})
const pluginNameRules = [
    (v: string) => !!v || 'Workflow tool name is required',
]
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/
const versionRules = [
    (v: string) => !!v || 'Version is required',
    (v: string) => semverRegex.test(v) || 'Version should be semantic versioning (e.g., 1.0.0)',
]
</script>

<style scoped>
.auth-card {
  border: 1px solid rgba(95, 214, 232, 0.28) !important;
  background: rgba(95, 214, 232, 0.04) !important;
}
</style>
