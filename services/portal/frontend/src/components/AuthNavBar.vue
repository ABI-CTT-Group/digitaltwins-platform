<template>
    <v-app-bar color="#0e3f5a" dark sticky>
        <v-app-bar-title class="text-white font-weight-bold">DigitalTWINS Portal</v-app-bar-title>
        
        <v-spacer></v-spacer>

        <div v-if="isLoggedIn" class="d-flex align-center gap-3">
            <div class="text-white text-right">
                <div class="text-subtitle2">{{ displayName }}</div>
                <v-chip size="small" class="mt-1" v-for="role in userRoles" :key="role" color="white" text-color="blue-darken-4">
                    {{ role }}
                </v-chip>
            </div>

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

                <v-list>
                    <v-list-item>
                        <div class="pa-2">
                            <p class="font-weight-bold">{{ displayName }}</p>
                            <p class="text-caption">{{ userEmail }}</p>
                        </div>
                    </v-list-item>
                    
                    <v-divider></v-divider>
                    
                    <v-list-item @click="handleLogout" class="text-error">
                        <v-list-item-title>
                            <v-icon icon="mdi-logout" class="mr-2"></v-icon>
                            Logout
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
</style>
