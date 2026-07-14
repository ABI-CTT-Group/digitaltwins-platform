// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import { useAuthStore } from '@/store/auth_store';
import { login } from '@/bootstrap/keycloak';

export function useAuthGuard() {
  const authStore = useAuthStore();
  const toast = useToast();

  function check(requiredRoles?: string[]): boolean {
    // No requireRoles defined → public card, skip auth entirely
    if (requiredRoles === undefined) return true;

    if (!authStore.isLoggedIn) {
      toast.warning('Please log in to access this feature.', {
        timeout: 4000,
        onClick: () => login(),
      });
      return false;
    }
    if (requiredRoles.length > 0) {
      const hasRequiredRole = requiredRoles.some(r => authStore.userRoles.includes(r));
      if (!hasRequiredRole) {
        toast.warning(`This feature requires the role: ${requiredRoles.join(' / ')}.`);
        return false;
      }
    }
    return true;
  }

  return { check };
}
