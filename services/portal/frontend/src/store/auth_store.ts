import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import {
  isAuthenticated,
  getUserInfo,
  getUserRoles,
  hasRole,
  logout as keycloakLogout,
  getAccessToken,
} from '@/plugins/keycloak';

interface UserInfo {
  username?: string;
  email?: string;
  givenName?: string;
  familyName?: string;
  roles: string[];
}

export const useAuthStore = defineStore('auth', () => {
  const isLoggedIn = ref<boolean>(isAuthenticated());
  const user = ref<UserInfo | null>(null);
  const accessToken = ref<string | undefined>(undefined);

  // Computed properties
  const hasAdminRole = computed(() => userRoles.value.includes('admin') || hasRole('admin'));
  const hasResearcherRole = computed(() => userRoles.value.includes('researcher') || hasRole('researcher'));
  const hasClinicianRole = computed(() => userRoles.value.includes('clinician') || hasRole('clinician'));
  const userRoles = computed(() => user.value?.roles?.length ? user.value.roles : getUserRoles());
  
  const displayName = computed(() => {
    if (!user.value) return '';
    const { givenName, familyName, username } = user.value;
    if (givenName && familyName) {
      return `${givenName} ${familyName}`;
    }
    return username || 'User';
  });

  function updateAuthState() {
    isLoggedIn.value = isAuthenticated();

    if (isLoggedIn.value) {
      user.value = getUserInfo();
      accessToken.value = getAccessToken();
      return;
    }

    user.value = null;
    accessToken.value = undefined;
  }

  async function logout() {
    try {
      if (isAuthenticated()) {
        await keycloakLogout();
      }
      sessionStorage.removeItem('access_token'); // Clean up any legacy data
      isLoggedIn.value = false;
      user.value = null;
      accessToken.value = undefined;
    } catch (error) {
      console.error('Logout error:', error);
      throw error;
    }
  }

  function canAccessDashboard(dashboardType: string): boolean {
    if (hasAdminRole.value) return true; // Admin can access all
    
    switch (dashboardType) {
      case 'researcher':
        return hasResearcherRole.value;
      case 'clinician':
        return hasClinicianRole.value;
      default:
        return false;
    }
  }

  return {
    isLoggedIn,
    user,
    accessToken,
    hasAdminRole,
    hasResearcherRole,
    hasClinicianRole,
    userRoles,
    displayName,
    updateAuthState,
    logout,
    canAccessDashboard,
  };
});
