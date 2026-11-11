<template>
    <div class="exit d-flex justify-center flex-wrap gap-4">
            <div class="roll-in-left">
                <v-btn
                    variant="tonal"
                    class="hover-animate heartbeat btn"
                    size="60"
                    @click="exit"
                    >
                    <v-icon
                        class="icon"
                        icon="mdi-exit-to-app"
                        size="25"
                        color="deep-orange"
                    >
                    </v-icon>
                </v-btn>
            </div>
        </div>
    <div v-if="error" class="pa-12 d-flex justify-center">
        <v-alert type="error" variant="tonal" max-width="640" :text="error" />
    </div>
    <div v-else-if="loading" class="pa-12 d-flex flex-column align-center ga-4">
        <v-progress-circular indeterminate color="primary" />
        <span>{{ loadingText }}</span>
    </div>
    <div v-else-if="app">
        <remote-component-app :src="app.path" :expose="app.expose" :context="context" @mounted="hideToken" />
    </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import RemoteComponentApp from '@/components/RemoteComponentApp.vue';
import { useRemoteAppStore } from '@/store/remote_store';
import { useDashboardGetAssayGuiContext } from '@/bootstrap/dashboard_api';
import { getAccessToken } from '@/bootstrap/keycloak';
import { buildVolViewQuery } from '@/utils/volviewParams';
import { assayFileCookie, clearAssayFileCookie } from '@/utils/assayFileCookie';
import { toLaunchContext } from '@/utils/launchContext';
import type { LaunchContext } from '@/models/types';
import { getApiErrorMessage } from '@/utils/common';
import { BackendStartError, ensureBackend } from '@/bootstrap/tool_api';

// Two ways in: the Tool Hub (persisted remoteApp store, no query) and a gui assay's
// Launch button (/tool-view?assay=<seek id>, opened in a new tab), which loads the
// assay's tool and input files from /dashboard/assay-gui-context. Either way the tool's
// backend, if it has one, is started (or deployed) before the tool mounts.
const route = useRoute();
const router = useRouter();
const { remoteApp } = useRemoteAppStore();
const assayId = typeof route.query.assay === 'string' ? route.query.assay : '';

const app = ref<{ path: string; expose: string } | null>(assayId ? null : remoteApp);
const context = ref<LaunchContext | undefined>();
const loading = ref(Boolean(app.value) || Boolean(assayId));
const loadingText = ref(assayId ? "Loading the assay's inputs…" : 'Opening the tool…');
const error = ref('');

onMounted(async () => {
    if (!loading.value) return;
    try {
        if (assayId) await loadAssay();
        if (app.value?.expose) {
            await ensureBackend(app.value.expose, (state) => {
                loadingText.value = state === 'deploying'
                    ? "Deploying the tool's backend (the first launch builds it, which can take a few minutes)…"
                    : "Starting the tool's backend…";
            });
        }
    } catch (e) {
        error.value = e instanceof BackendStartError ? `Launch failed: ${e.message}` : getApiErrorMessage(e, 'Launch');
    } finally {
        loading.value = false;
    }
});

async function loadAssay() {
    const ctx = await useDashboardGetAssayGuiContext(assayId);
    // VolView reads its inputs from the page query when it mounts, so set them before the
    // plugin loads (replaceState is client-side only), and let its plain fetch authenticate
    // through a cookie scoped to this assay's input-files path.
    history.replaceState(history.state, '', `${route.path}${buildVolViewQuery(ctx)}`);
    assayFileCookie(assayId, getAccessToken() ?? '');
    context.value = toLaunchContext(ctx, getAccessToken);
    app.value = ctx.tool;
}

onBeforeUnmount(() => {
    if (assayId) clearAssayFileCookie(assayId);
});

// Once the plugin has read the query, leave only the assay id in the address bar.
const hideToken = () => {
    if (assayId) history.replaceState(history.state, '', `${route.path}?assay=${encodeURIComponent(assayId)}`);
};

// A launched tab has no history to go back to.
const exit = () => (assayId ? window.close() : router.back());
</script>

<style scoped>
.exit{
    position: fixed;
    top: 10px;
    left: 50%;
    z-index: 99999;
}
.icon {
    transform: rotate(-180deg);
}
/* .btn {
    background-color: rgba(255,255,255, 0.2);
} */

</style>
