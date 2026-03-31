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
                        variant="text"
                        v-bind="props"
                        size="large"
                        color="white"
                        class="text-capitalize user-menu-btn"
                    >
                        <div class="d-flex flex-column align-center">
                            <v-icon icon="mdi-account-circle"></v-icon>
                            <span class="text-truncate user-name-text">{{ firstName }}</span>
                        </div>
                    </v-btn>
                </template>

                <v-list class="user-menu-list">
                    <v-list-item class="user-info-item">
                        <div class="pa-5 w-100">
                            <div class="d-flex align-center gap-3 mb-4">
                                <v-icon icon="mdi-account-circle" size="40" class="text-blue-lighten-1"></v-icon>
                                <div class="flex-grow-1">
                                    <p class="font-weight-bold text-white mb-1" style="font-size: 16px; letter-spacing: 0.3px;">{{ displayName }}</p>
                                    <p class="text-caption text-blue-lighten-1 mb-0" style="font-size: 12px; opacity: 0.85;">{{ userEmail }}</p>
                                </div>
                            </div>
                            <v-divider class="my-4" style="border-color: rgba(66, 165, 245, 0.1);"></v-divider>
                            <div>
                                <p class="text-caption font-weight-bold text-blue-lighten-2 mb-3" style="font-size: 12px; letter-spacing: 0.5px; text-transform: uppercase; opacity: 0.8;">Assigned Roles</p>
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
                            <v-icon icon="mdi-logout" class="mr-2" style="color: #e74c3c;"></v-icon>
                            <span style="color: #e74c3c; font-weight: 500;">Logout</span>
                        </v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
        </div>

        <div v-else class="d-flex gap-2">
            <v-btn class="text-white" variant="text" @click="handleLogin">
                <v-icon icon="mdi-login" class="mr-1"></v-icon>
                Login
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
const firstName = computed(() => authStore.displayName?.split(' ')[0] || '');
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
    background-color: #1a2332 !important;
    border-radius: 12px !important;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25), 0 0 1px rgba(0, 0, 0, 0.1) !important;
    min-width: 360px;
    overflow: hidden;
    border: 1px solid rgba(66, 165, 245, 0.1);
}

.user-info-item {
    background: linear-gradient(180deg, #242f42 0%, #1a2332 100%) !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    border-bottom: 1px solid rgba(66, 165, 245, 0.15);
}

.user-info-item:hover {
    background: linear-gradient(180deg, #2a3947 0%, #242f42 100%) !important;
}

.menu-role-chip {
    background-color: rgba(66, 165, 245, 0.15) !important;
    color: #42a5f5 !important;
    font-weight: 600;
    border: 1px solid rgba(66, 165, 245, 0.3);
}

.logout-item {
    background-color: transparent !important;
    padding: 0 !important;
    height: 48px;
    display: flex;
    align-items: center;
    padding-left: 16px !important;
    transition: all 0.3s ease;
    border-top: 1px solid rgba(66, 165, 245, 0.1);
}

.logout-item:hover {
    background-color: rgba(231, 76, 60, 0.08) !important;
    border-left: 3px solid #e74c3c;
    padding-left: 13px !important;
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

.user-menu-btn {
    min-width: 70px;
}

.user-name-text {
    font-size: 10px;
    font-weight: 500;
    max-width: 60px;
    line-height: 1;
}
</style>
