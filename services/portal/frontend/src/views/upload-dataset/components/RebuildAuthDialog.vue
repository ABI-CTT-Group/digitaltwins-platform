<template>
  <v-dialog v-model="open" max-width="560" persistent transition="dialog-bottom-transition">
    <v-card rounded="lg" flat class="overflow-hidden auth-dialog">
      <v-card-title class="d-flex align-center px-6 pt-6 pb-4 text-h5 dialog-title">
        <v-icon color="#5fd6e8" class="mr-3" size="32">mdi-shield-refresh-outline</v-icon>
        Rebuild Access
      </v-card-title>

      <v-card-text class="px-6 pb-6">
        <v-alert
          type="info"
          variant="tonal"
          color="#5fd6e8"
          density="comfortable"
          class="mb-6 rounded-md text-body-2"
          icon="mdi-information-outline"
        >
          Tokens are not persisted server-side. Every rebuild needs them re-supplied.
          Leave blank if this repository is public.
        </v-alert>

        <!-- Provider Chip area -->
        <v-sheet class="d-flex align-center mb-6 pa-4 rounded-md provider-sheet">
          <v-icon color="#9fb4bf" class="mr-3">mdi-source-branch</v-icon>
          <span class="text-body-1 font-weight-medium provider-label">Detected provider:</span>
          <v-spacer></v-spacer>
          <v-chip size="default" color="#5fd6e8" variant="tonal" class="font-weight-bold px-4">
            <v-icon start size="small">{{ providerIcon }}</v-icon>
            {{ providerLabel }}
          </v-chip>
        </v-sheet>

        <v-text-field
          v-model="token"
          :type="showPlain ? 'text' : 'password'"
          :append-inner-icon="showPlain ? 'mdi-eye-off' : 'mdi-eye'"
          @click:append-inner="showPlain = !showPlain"
          label="Personal Access Token"
          placeholder="ghp_... / glpat-... / app password"
          variant="outlined"
          color="#5fd6e8"
          density="comfortable"
          prepend-inner-icon="mdi-key-outline"
          clearable
          autofocus
          class="mb-4"
          hide-details="auto"
        />

        <v-expand-transition>
          <v-text-field
            v-if="sourceType === 'git_generic'"
            v-model="authUsername"
            label="Username (self-hosted git only)"
            placeholder="HTTP basic-auth username"
            variant="outlined"
            color="#5fd6e8"
            density="comfortable"
            prepend-inner-icon="mdi-account-outline"
            clearable
            class="mb-4"
            hide-details="auto"
          />
        </v-expand-transition>

        <v-sheet
          class="pa-3 rounded-md transition-swing mt-2 ssl-sheet"
          :class="trustSelfSigned ? 'ssl-sheet--on' : ''"
        >
          <v-checkbox
            v-model="trustSelfSigned"
            hide-details
            density="compact"
            color="error"
          >
            <template #label>
              <div class="d-flex flex-column ml-1 py-1">
                <span class="text-body-1 font-weight-medium" :class="trustSelfSigned ? 'text-error' : 'ssl-label'">
                  Trust self-signed certificate
                </span>
                <span class="text-caption font-weight-medium d-flex align-center mt-1" :class="trustSelfSigned ? 'text-error' : 'ssl-hint'">
                  <v-icon size="x-small" class="mr-1" :color="trustSelfSigned ? 'error' : '#9fb4bf'">mdi-alert-outline</v-icon>
                  MITM risk — only enable for trusted internal networks
                </span>
              </div>
            </template>
          </v-checkbox>
        </v-sheet>
      </v-card-text>
      
      <!-- Status hint: explains what the Build button will actually do given
           the current state of token/username. Drives Build button label
           and disabled state below — prevents the "I clicked Build Now
           without filling token, why did it fail" confusion. -->
      <div class="px-6 pb-2 text-center text-caption" :class="hintClass">
        <v-icon size="x-small" class="mr-1">{{ hintIcon }}</v-icon>
        {{ hintText }}
      </div>

      <v-divider class="mb-2" :thickness="2"></v-divider>

      <v-card-actions class="px-6 py-4 justify-center">
        <v-btn
          color="#9fb4bf"
          text="Cancel"
          variant="text"
          :min-width="150"
          rounded="lg"
          class="text-none mx-3"
          :disabled="busy"
          @click="cancel"
        />
        <v-btn
          :color="buildButtonColor"
          :text="buildButtonLabel"
          variant="tonal"
          :min-width="200"
          rounded="lg"
          class="text-none mx-3"
          :loading="busy"
          :disabled="busy || !canSubmit"
          @click="submit"
        />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { SourceType, TransientAuth } from '@/models/types'

const props = defineProps<{
  modelValue: boolean
  sourceType?: SourceType | null
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'submit', auth: TransientAuth): void
  (e: 'cancel'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const token = ref('')
const authUsername = ref('')
const trustSelfSigned = ref(false)
const showPlain = ref(false)
const sourceType = computed(() => props.sourceType ?? 'github')

const providerLabel = computed(() => {
  switch (sourceType.value) {
    case 'github': return 'GitHub'
    case 'gitlab': return 'GitLab'
    case 'bitbucket': return 'Bitbucket'
    case 'git_generic': return 'Self-hosted / Generic Git'
    default: return String(sourceType.value)
  }
})

const providerIcon = computed(() => {
  switch (sourceType.value) {
    case 'github': return 'mdi-github'
    case 'gitlab': return 'mdi-gitlab'
    case 'bitbucket': return 'mdi-bitbucket'
    case 'git_generic': return 'mdi-git'
    default: return 'mdi-source-repository'
  }
})

// Build-button state machine. Computed off (sourceType, token, authUsername)
// so the user always sees what'll happen and can't accidentally fire an
// auth-less build for a provider that requires it.
//
// GitHub deliberately allows empty-token submission because we can't tell
// from the URL alone whether the repo is public — empty token means "try
// anonymous". GitLab / Bitbucket / Generic require explicit token because
// the user clearly entered the rebuild dialog already (means they expect
// to authenticate); a missing token is almost certainly a UX slip, not
// intent to do an anonymous rebuild.
const _genericNeedsUsername = computed(() =>
  sourceType.value === 'git_generic' && !!token.value && !authUsername.value,
)
const _tokenRequired = computed(() =>
  sourceType.value !== 'github' && !token.value,
)

const canSubmit = computed(() => {
  if (_tokenRequired.value) return false
  if (_genericNeedsUsername.value) return false
  return true
})

const buildButtonLabel = computed(() => {
  if (_tokenRequired.value) return 'Token Required'
  if (_genericNeedsUsername.value) return 'Username Required'
  if (token.value) return 'Build with Token'
  return 'Build as Public'  // github + empty token
})

const buildButtonColor = computed(() => {
  // Subdued color when not actionable; aqua accent when ready.
  if (!canSubmit.value) return '#9fb4bf'
  return '#5fd6e8'
})

const hintText = computed(() => {
  if (_tokenRequired.value) {
    return `${providerLabel.value} requires a token to clone — anonymous access isn't supported here.`
  }
  if (_genericNeedsUsername.value) {
    return 'Self-hosted git needs a username (HTTP basic-auth) to use the token.'
  }
  if (token.value) {
    return 'Will clone with the token via askpass — token is sent once, not stored.'
  }
  return 'Will attempt anonymous clone — works for public GitHub repos.'
})

const hintIcon = computed(() => {
  if (!canSubmit.value) return 'mdi-alert-circle-outline'
  if (token.value) return 'mdi-key-outline'
  return 'mdi-information-outline'
})

const hintClass = computed(() => {
  if (!canSubmit.value) return 'text-warning'
  if (token.value) return 'text-success'
  return 'hint-muted'
})

// Reset on open so a stale token from a previous dialog can never leak.
watch(open, (v) => {
  if (v) {
    token.value = ''
    authUsername.value = ''
    trustSelfSigned.value = false
    showPlain.value = false
  }
})

const submit = () => {
  emit('submit', {
    token: token.value || undefined,
    authUsername: authUsername.value || undefined,
    verifySsl: trustSelfSigned.value ? false : undefined,
  })
}

const cancel = () => {
  emit('cancel')
  emit('update:modelValue', false)
}
</script>

<style scoped>
.auth-dialog {
  background: rgba(8, 18, 26, 0.97) !important;
  border: 1px solid rgba(120, 200, 220, 0.18);
  color: #e9f2f5;
}
.dialog-title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  color: #fff;
}
.provider-sheet {
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(120, 200, 220, 0.14);
}
.provider-label { color: #c3d2d8; }
.ssl-sheet {
  background: transparent !important;
  border: 1px solid rgba(120, 200, 220, 0.14);
}
.ssl-sheet--on {
  background: rgba(255, 107, 107, 0.06) !important;
  border-color: rgba(255, 107, 107, 0.45);
}
.ssl-label { color: #c3d2d8; }
.ssl-hint { color: #9fb4bf; }
.hint-muted { color: #7f97a1; }
</style>
