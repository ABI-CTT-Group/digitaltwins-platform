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
  const isLoggedIn = ref<boolean>(isAuthenticated() || !!sessionStorage.getItem('access_token'));
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

  function parseJwt(token: string): any | null {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => `%${('00' + c.charCodeAt(0).toString(16)).slice(-2)}`)
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch {
      return null;
    }
  }

  function filterRoles(roles: string[]): string[] {
    const validRoles = ['admin', 'researcher', 'clinician'];
    return roles.filter((role) => validRoles.includes(role));
  }

  function updateAuthState() {
    const keycloakAuthed = isAuthenticated();
    const sessionToken = sessionStorage.getItem('access_token');
    isLoggedIn.value = keycloakAuthed || !!sessionToken;

    if (keycloakAuthed) {
      user.value = getUserInfo();
      accessToken.value = getAccessToken();
      return;
    }

    if (sessionToken) {
      const payload = parseJwt(sessionToken);
      const allRoles = payload?.realm_access?.roles || payload?.roles || [];
      user.value = payload
        ? {
            username: payload.preferred_username || payload.username,
            email: payload.email,
            givenName: payload.given_name,
            familyName: payload.family_name,
            roles: filterRoles(allRoles),
          }
        : null;
      accessToken.value = sessionToken;
      return;
    }

    user.value = null;
    accessToken.value = undefined;
  }

  async function logout() {
    try {
      const keycloakAuthed = isAuthenticated();
      if (keycloakAuthed) {
        await keycloakLogout();
      }
      sessionStorage.removeItem('access_token');
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
