<template>
    <div class="fill-height d-flex flex-column justify-center align-center">
        <div class="h-70">
            <div class="mx-5 my-10 text-center">
                <h1 class=" title">DigitalTWINS AI Platform</h1>
            </div>
            <div class="mx-auto rounded w-66 form-login">
                <v-card class="pa-8 transparent-card">
                    <v-card-title class="text-center mb-6">
                        {{ isAuthenticated ? 'Welcome Back!' : 'Sign In' }}
                    </v-card-title>

                    <!-- Authenticated User Card -->
                    <div v-if="isAuthenticated" class="text-center">
                        <v-avatar size="80" class="mb-4">
                            <v-icon icon="mdi-account-circle" size="80"></v-icon>
                        </v-avatar>
                        <div class="mb-4">
                            <p class="text-h6">{{ displayName }}</p>
                            <p class="text-subtitle2 text-grey">{{ userEmail }}</p>
                        </div>
                        <div class="mb-6">
                            <v-chip v-for="role in userRoles" :key="role" class="mr-2 mb-2" color="primary">
                                {{ role }}
                            </v-chip>
                        </div>
                        <v-btn
                            color="#009688"
                            size="large"
                            @click="handleEnter"
                            class="mb-3"
                            block
                        >
                            Enter Portal
                        </v-btn>
                        <v-btn
                            color="error"
                            variant="outlined"
                            @click="handleLogout"
                            block
                        >
                            Logout
                        </v-btn>
                    </div>

                    <!-- Login Form -->
                    <div v-else>
                        <v-form @submit.prevent="handleFormLogin" class="login-form">
                            <v-text-field
                                v-model="username"
                                label="Username"
                                type="text"
                                outlined
                                required
                                class="mb-4"
                                :disabled="loading"
                                @keyup.enter="handleFormLogin"
                            ></v-text-field>

                            <v-text-field
                                v-model="password"
                                label="Password"
                                type="password"
                                outlined
                                required
                                class="mb-6"
                                :disabled="loading"
                                @keyup.enter="handleFormLogin"
                            ></v-text-field>

                            <v-alert v-if="errorMessage" type="error" class="mb-4">
                                {{ errorMessage }}
                            </v-alert>

                            <v-btn
                                color="#009688"
                                size="large"
                                type="submit"
                                block
                                :loading="loading"
                                :disabled="!username || !password || loading"
                            >
                                Sign In
                            </v-btn>
                        </v-form>

                        <v-divider class="my-6">
                            <span class="text-grey">OR</span>
                        </v-divider>

                        <v-btn
                            color="primary"
                            size="large"
                            block
                            variant="outlined"
                            prepend-icon="mdi-shield-account"
                            @click="handleKeycloakLogin"
                            :disabled="loading"
                            class="keycloak-btn"
                        >
                            Sign In with Keycloak
                        </v-btn>
                    </div>
                </v-card>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/auth_store';
import { getKeycloak, isAuthenticated as checkAuthenticated, logout as keycloakLogout } from '@/plugins/keycloak';
import http from '@/plugins/http';

const router = useRouter();
const authStore = useAuthStore();

const isAuthenticated = ref(false);
const username = ref('');
const password = ref('');
const loading = ref(false);
const errorMessage = ref('');
const errorTimerId = ref<number | undefined>(undefined);

const displayName = computed(() => authStore.displayName);
const userEmail = computed(() => authStore.user?.email || '');
const userRoles = computed(() => authStore.userRoles);

onMounted(async () => {
    // Update auth state
    authStore.updateAuthState();
    isAuthenticated.value = checkAuthenticated();
});

const showLoginError = (message: string) => {
    errorMessage.value = message;

    if (errorTimerId.value !== undefined) {
        window.clearTimeout(errorTimerId.value);
    }

    errorTimerId.value = window.setTimeout(() => {
        errorMessage.value = '';
        username.value = '';
        password.value = '';
        errorTimerId.value = undefined;
    }, 5000);
};

// Form-based login
const handleFormLogin = async () => {
    if (!username.value || !password.value) {
        errorMessage.value = 'Please enter username and password';
        return;
    }

    loading.value = true;
    errorMessage.value = '';

    try {
        const response = await http.post('/auth/login-keycloak', {
            username: username.value,
            password: password.value,
        });

        // Store the access token
        if (response.access_token) {
            sessionStorage.setItem('access_token', response.access_token);
            
            // Update auth store and redirect
            authStore.updateAuthState();
            await router.push({ name: 'Home' });
        } else {
            showLoginError('Login failed: No access token received');
        }
    } catch (error: any) {
        console.error('Login error:', error);
        showLoginError(error.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
        loading.value = false;
    }
};

// Keycloak direct login (no backend credentials)
const handleKeycloakLogin = async () => {
    const keycloak = getKeycloak();
    if (keycloak) {
        try {
            // This redirects to Keycloak login page
            // User credentials are handled entirely by Keycloak
            await keycloak.login({
                redirectUri: window.location.origin + '/home'
            });
        } catch (error) {
            console.error('Keycloak login failed:', error);
            errorMessage.value = 'Keycloak login failed. Please try again.';
        }
    } else {
        errorMessage.value = 'Keycloak is not initialized. Please refresh the page.';
    }
};

// Logout
const handleLogout = async () => {
    try {
        await authStore.logout();
        // Redirect to login after logout
        await router.push({ name: 'Login' });
    } catch (error) {
        console.error('Logout error:', error);
    }
};

// Enter portal
const handleEnter = async () => {
    await router.push({ name: 'Home' });
};
</script>

<style scoped>
.form-login {
    min-width: 30rem;
}

.title {
    line-height: 1.6;
    font-size: 2.8rem;
}

.login-form {
    width: 100%;
}

.transparent-card {
    background-color: transparent !important;
    backdrop-filter: blur(2px);
}

.keycloak-btn {
    border-width: 2px !important;
    font-weight: 500;
}

.keycloak-btn:hover {
    background-color: rgba(33, 150, 243, 0.1);
    transform: translateY(-2px);
    transition: all 0.3s ease;
}
</style>

