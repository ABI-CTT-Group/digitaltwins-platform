<template>
    <v-app-bar class="nav-bar" :class="{ 'is-scrolled': scrolled }" color="transparent" :elevation="0" sticky>
        <router-link to="/" class="brand">
            <span class="brand__mark" aria-hidden="true">
                <svg width="30" height="26" viewBox="0 0 64 64" fill="none">
                    <defs>
                        <linearGradient id="nav-dt-cyan" x1="6" y1="14" x2="40" y2="50" gradientUnits="userSpaceOnUse">
                            <stop offset="0" stop-color="#8deff6"/>
                            <stop offset="1" stop-color="#3fb6d6"/>
                        </linearGradient>
                        <linearGradient id="nav-dt-mint" x1="24" y1="14" x2="58" y2="50" gradientUnits="userSpaceOnUse">
                            <stop offset="0" stop-color="#86e7b0"/>
                            <stop offset="1" stop-color="#3fb589"/>
                        </linearGradient>
                        <linearGradient id="nav-dt-core" x1="27" y1="27" x2="37" y2="37" gradientUnits="userSpaceOnUse">
                            <stop offset="0" stop-color="#9ff0f7"/>
                            <stop offset="1" stop-color="#8fe9b6"/>
                        </linearGradient>
                    </defs>
                    <circle cx="24" cy="32" r="13" fill="none" stroke="url(#nav-dt-cyan)" stroke-width="4"/>
                    <circle cx="40" cy="32" r="13" fill="none" stroke="url(#nav-dt-mint)" stroke-width="4"/>
                    <circle cx="32" cy="32" r="4.6" fill="url(#nav-dt-core)"/>
                </svg>
            </span>
            <span class="brand__word">ABI Digital Twins<span class="brand__dim"> Platform</span></span>
        </router-link>

        <v-spacer></v-spacer>

        <div v-if="isLoggedIn" class="d-flex align-center">
            <v-menu>
                <template v-slot:activator="{ props }">
                    <button type="button" v-bind="props" class="user-trigger">
                        <span class="user-trigger__ava">{{ initials }}</span>
                        <span class="user-trigger__name">{{ firstName }}</span>
                        <v-icon icon="mdi-chevron-down" size="16"></v-icon>
                    </button>
                </template>

                <v-list class="user-menu-list">
                    <v-list-item class="user-info-item">
                        <div class="menu-head">
                            <span class="menu-ava">{{ initials }}</span>
                            <div class="menu-id">
                                <p class="menu-name">{{ displayName }}</p>
                                <p class="menu-email">{{ userEmail }}</p>
                            </div>
                        </div>
                        <div class="menu-roles">
                            <p class="menu-roles__label">Assigned roles</p>
                            <div class="menu-roles__chips">
                                <span v-for="role in userRoles" :key="role" class="menu-role-chip">
                                    <v-icon icon="mdi-shield-account-outline" size="12" class="mr-1"></v-icon>{{ role }}
                                </span>
                            </div>
                        </div>
                    </v-list-item>

                    <v-list-item @click="handleLogout" class="logout-item">
                        <v-icon icon="mdi-logout-variant" size="18" class="mr-2"></v-icon>
                        <span>Logout</span>
                    </v-list-item>
                </v-list>
            </v-menu>
        </div>

        <button v-else type="button" class="signin" @click="handleLogin">Sign in</button>
    </v-app-bar>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAuthStore } from '@/store/auth_store';
import { login } from '@/bootstrap/keycloak';
import { useScrollState } from '@/composables/useScrollState';

const authStore = useAuthStore();
const { scrolled } = useScrollState();

const isLoggedIn = computed(() => authStore.isLoggedIn);
const displayName = computed(() => authStore.displayName);
const firstName = computed(() => authStore.displayName?.split(' ')[0] || '');
const userEmail = computed(() => authStore.user?.email || '');
const userRoles = computed(() => authStore.userRoles);
const initials = computed(() => {
    const parts = (authStore.displayName?.trim() || '').split(/\s+/).filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || 'U';
});

// Both of these hand the browser to Keycloak, which redirects back on its own —
// there is nothing to route to afterwards.
const handleLogout = async () => {
    try {
        await authStore.logout();
    } catch (error) {
        console.error('Logout error:', error);
    }
};

const handleLogin = async () => {
    try {
        await login();
    } catch (error) {
        console.error('Login failed:', error);
    }
};
</script>

<style scoped>
/* Transparent by default — the static aurora (Default.vue) shows through, so
   nav + page read as one field. A frosted tint fades in only after scroll.
   Backdrop-filter exists only in the scrolled state, and content scrolls below
   the bar (never under it), so it stays cheap. */
.nav-bar {
    background: transparent !important;
    border-bottom: 1px solid transparent;
    transition: background 0.35s ease, backdrop-filter 0.35s ease, border-color 0.35s ease;
}
.nav-bar.is-scrolled {
    background: rgba(10, 16, 30, 0.6) !important;
    backdrop-filter: blur(14px) saturate(130%);
    -webkit-backdrop-filter: blur(14px) saturate(130%);
    border-bottom-color: rgba(160, 190, 200, 0.14);
}

.brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-left: 12px;
    text-decoration: none;
}
.brand__mark { color: #e6edf0; display: inline-flex; }
.brand__word {
    color: #e6edf0;
    font-family: "Nunito", sans-serif;
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 0.2px;
}
.brand__dim { color: #9aabb3; font-weight: 500; }

.signin {
    margin-right: 14px;
    padding: 7px 16px;
    border-radius: 8px;
    border: 1px solid rgba(160, 190, 200, 0.3);
    background: transparent;
    color: #cdd8dd;
    font-family: "Nunito", sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color 0.25s ease, color 0.25s ease, background 0.25s ease;
}
.signin:hover { border-color: rgba(95, 214, 232, 0.5); color: #eafaff; background: rgba(95, 214, 232, 0.08); }

.user-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: 12px;
    padding: 5px 10px 5px 6px;
    border-radius: 999px;
    border: 1px solid rgba(160, 190, 200, 0.18);
    background: rgba(255, 255, 255, 0.03);
    color: #cdd8dd;
    cursor: pointer;
    font-family: "Nunito", sans-serif;
    transition: border-color 0.25s ease, background 0.25s ease;
}
.user-trigger:hover { border-color: rgba(95, 214, 232, 0.4); background: rgba(255, 255, 255, 0.05); }
.user-trigger__ava {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #1d2735;
    display: grid;
    place-items: center;
    font-size: 0.7rem;
    font-weight: 700;
    color: #cdd8dd;
}
.user-trigger__name { font-size: 0.85rem; }

/* ---- User dropdown — aurora glass, aqua accent ---- */
.user-menu-list {
    margin-top: 8px;
    padding: 0 !important;
    min-width: 300px;
    overflow: hidden;
    border-radius: 14px !important;
    background: rgba(8, 18, 26, 0.97) !important;
    border: 1px solid rgba(95, 214, 232, 0.18);
    box-shadow: 0 18px 48px -16px rgba(0, 0, 0, 0.75) !important;
    font-family: "Nunito", sans-serif;
}

.user-info-item {
    padding: 18px 18px 16px !important;
    background: transparent !important;
}
.menu-head { display: flex; align-items: center; gap: 12px; }
.menu-ava {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 0.95rem;
    font-weight: 700;
    color: #06121a;
    background: linear-gradient(135deg, #5fd6e8, #3aa6d9);
}
.menu-id { min-width: 0; }
.menu-name { margin: 0; font-weight: 700; font-size: 0.95rem; color: #fff; letter-spacing: 0.2px; }
.menu-email { margin: 2px 0 0; font-size: 0.78rem; color: #8ba0a9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.menu-roles {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid rgba(120, 200, 220, 0.12);
}
.menu-roles__label {
    margin: 0 0 9px;
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #5fd6e8;
    opacity: 0.85;
}
.menu-roles__chips { display: flex; flex-wrap: wrap; gap: 7px; }
.menu-role-chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    color: #cfe7ee;
    background: rgba(95, 214, 232, 0.12);
    border: 1px solid rgba(95, 214, 232, 0.3);
}

.logout-item {
    display: flex !important;
    align-items: center;
    min-height: 46px !important;
    padding: 0 18px !important;
    color: #f0a6a6;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    border-top: 1px solid rgba(120, 200, 220, 0.1);
    transition: background 0.25s ease, color 0.25s ease;
}
.logout-item:hover {
    background: rgba(240, 120, 120, 0.1) !important;
    color: #ff8a8a;
}
</style>
