<template>
    <v-app-bar color="#0e3f5a" dark sticky>
        <router-link to="/" class="home-icon-link">
            <div class="d-flex align-center cursor-pointer pa-2 home-icon">
                <v-icon icon="mdi-home-outline" size="large" class="text-blue-darken-2 mr-2"></v-icon>
                <h3 class="text-white font-weight-bold mb-0">DigitalTWINS AI Platform</h3>
            </div>
        </router-link>
        
        <v-spacer></v-spacer>

        <img 
            src="@/assets/images/abi.png" 
            alt="ABI Logo" 
            class="navbar-logo"
        />

        <div v-if="isLoggedIn" class="d-flex align-center gap-4">
            <v-divider vertical class="mx-2"></v-divider>

            <v-menu>
                <template v-slot:activator="{ props }">
                    <v-btn
                        icon="mdi-account-circle"
                        variant="text"
                        v-bind="props"
                        size="large"
                        color="white"
                    ></v-btn>
                </template>

                <v-list class="user-menu-list">
                    <v-list-item class="user-info-item">
                        <div class="pa-4 w-100">
                            <div class="d-flex align-center gap-2 mb-3">
                                <v-icon icon="mdi-account-circle" size="x-large" class="text-blue-darken-4"></v-icon>
                                <div>
                                    <p class="font-weight-bold text-blue-darken-4 mb-0" style="font-size: 15px;">{{ displayName }}</p>
                                    <p class="text-caption text-blue-darken-3 mb-0">{{ userEmail }}</p>
                                </div>
                            </div>
                            <v-divider class="my-3"></v-divider>
                            <div>
                                <p class="text-caption font-weight-bold text-blue-darken-4 mb-2">Assigned Roles</p>
                                <div class="d-flex flex-wrap gap-2">
                                    <v-chip size="small" v-for="role in userRoles" :key="role" class="menu-role-chip">
                                        <v-icon icon="mdi-badge-account" size="x-small" class="mr-1"></v-icon>
                                        {{ role }}
                                    </v-chip>
                                </div>
                            </div>
                        </div>
                    </v-list-item>
                    
                    <v-divider></v-divider>
                    
                    <v-list-item @click="handleLogout" class="logout-item">
                        <v-list-item-title class="d-flex align-center">
                            <v-icon icon="mdi-logout" class="mr-2 text-error"></v-icon>
                            <span class="text-error">Logout</span>
                        </v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
        </div>

        <div v-else class="d-flex gap-2">
            <v-btn class="text-white" variant="text" @click="handleLogin">
                <v-icon icon="mdi-login" class="mr-1"></v-icon>
                Sign In
            </v-btn>
        </div>
    </v-app-bar>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/auth_store';
import { getKeycloak } from '@/plugins/keycloak';

const router = useRouter();
const authStore = useAuthStore();

const isLoggedIn = computed(() => authStore.isLoggedIn);
const displayName = computed(() => authStore.displayName);
const userEmail = computed(() => authStore.user?.email || '');
const userRoles = computed(() => authStore.userRoles);

const handleLogout = async () => {
    try {
        await authStore.logout();
        await router.push({ name: 'Login' });
    } catch (error) {
        console.error('Logout error:', error);
    }
};

const handleLogin = async () => {
    const keycloak = getKeycloak();
    if (keycloak) {
        try {
            await keycloak.login();
        } catch (error) {
            console.error('Login failed:', error);
        }
    }
};
</script>

<style scoped>
.gap-3 {
    gap: 12px;
}

.gap-2 {
    gap: 8px;
}

.home-icon-link {
    text-decoration: none;
    color: inherit;
    display: flex;
    align-items: center;
    padding-left: 12px;
}

.home-icon {
    cursor: pointer;
    transition: background-color 0.2s ease;
    border-radius: 4px;
}

.home-icon:hover {
    background-color: #0a2f47;
}

.user-menu-list {
    background-color: #ffffff !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12) !important;
    min-width: 320px;
}

.user-info-item {
    background-color: #ffffff !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.user-info-item:hover {
    background-color: #ffffff !important;
}

.menu-role-chip {
    background-color: #e3f2fd !important;
    color: #0d47a1 !important;
    font-weight: 500;
}

.logout-item {
    background-color: #ffffff !important;
    padding: 0 !important;
    height: 48px;
    display: flex;
    align-items: center;
    padding-left: 16px !important;
    transition: background-color 0.2s ease;
}

.logout-item:hover {
    background-color: #ffebee !important;
}

.user-profile-card {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    border-left: 3px solid #42a5f5;
    backdrop-filter: blur(10px);
}

.user-info-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.user-name {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.3px;
}

.user-roles-container {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
}

.role-chip {
    background-color: #42a5f5 !important;
    color: #ffffff !important;
    font-weight: 500;
}

.navbar-logo {
    height: auto;
    max-height: 85%;
    width: auto;
    object-fit: contain;
    margin-right: 16px;
}
</style>
