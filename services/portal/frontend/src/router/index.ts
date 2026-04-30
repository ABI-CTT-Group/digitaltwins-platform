// Composables
import {
  createRouter,
  createWebHistory,
  createWebHashHistory,
  RouteRecordRaw,
} from "vue-router";
import { useAuthStore } from "@/store/auth_store";
import { isAuthenticated } from "@/bootstrap/keycloak";
import Home from "@/views/home/index.vue";
import Dashboard from "@/views/study/index.vue";
import TutorialDashboard from "@/views/tutorial/index.vue";
import CatalogueDashboardView from "@/views/catalogue/catalogue-dashboard-view.vue";
import ToolsViewer from "@/views/catalogue/tools-viewer.vue";
import Layout from "@/layouts/Default.vue";
import LaunchedAssayOverview from "@/views/study/assay-overview.vue";
import UploadDataset from "@/views/upload-dataset/index.vue";
import UploadToolDataset from "@/views/upload-dataset/workflow-tool/index.vue";
import UploadWorkflowDataset from "@/views/upload-dataset/workflow/index.vue";
import PluginHome from "@/views/tool-plugin/index.vue";
import ToolPluginView from "@/views/tool-plugin/tool-plugin-view.vue";


const routes = [
  {
    path:"/",
    component: Layout,
    children:[
          {
            path: "",
            name: "Home",
            component: Home,
          },
          {
            path: "/dashboard:dashboardType",
            name: "Dashboard",
            component: Dashboard,
            meta: { requiresAuth: true, showBack: true },
          },
          {
            path: "/how-it-works",
            name: "TutorialDashboard",
            component: TutorialDashboard,
            meta: { showBack: true },
          },
          {
            path: "/catalogue-dashboard",
            name: "CatalogueDashboardView",
            component: CatalogueDashboardView,
            meta: { requiresAuth: true, showBack: true },
          },
          {
            path: "/catalogue-dashboard-tools",
            name: "ToolsViewer",
            component: ToolsViewer,
            meta: { requiresAuth: true, showBack: true },
          },
          {
            path: "/launched-assay",
            name: "LaunchedAssayOverview",
            component: LaunchedAssayOverview,
            meta: { requiresAuth: true, showBack: true },
          },
          {
            path: "/upload-dataset",
            name: "UploadDataset",
            component: UploadDataset,
            meta: { requiresAuth: true, showBack: true },
            children:[
              {
                path: "/upload-tool-dataset",
                name: "UploadToolDataset",
                component: UploadToolDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin'], showBack: true },
              },
              {
                path: "/upload-workflow-dataset",
                name: "UploadWorkflowDataset",
                component: UploadWorkflowDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin'], showBack: true },
              },
            ]
          },
          {
            path: "/plugin-home",
            name: "PluginHome",
            component: PluginHome,
            meta: { requiresAuth: true },
          },
    ]
  },
  {
    path: "/tool-view",
    name: "ToolPluginView",
    component: ToolPluginView,
    meta: { requiresAuth: true },
  }
];


// use for the github repo

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

// Navigation guard for authentication
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();
  const requiresAuth = to.matched.some(r => r.meta?.requiresAuth);
  const requiresRoles = (to.meta?.requiresRoles ?? []) as string[];
  const hasToken = !!sessionStorage.getItem('access_token');
  authStore.updateAuthState();

  if (requiresAuth) {
    if (!isAuthenticated() && !hasToken) {
      console.warn('⚠️ Router Guard: NOT authenticated & no sessionStorage token → redirecting to Home');
      next({ name: 'Home' });
      return;
    }

    // Role guard — hard block for routes that require a specific role
    if (requiresRoles.length > 0) {
      const hasRequiredRole = requiresRoles.some(r => authStore.userRoles.includes(r));
      if (!hasRequiredRole) {
        next({ name: 'Home' });
        return;
      }
    }

    if (to.name === 'Dashboard') {
      const dashboardType = String(to.params?.dashboardType || '');

      if (dashboardType === 'study') {
        if (!authStore.hasAdminRole && !authStore.hasResearcherRole) {
          if (authStore.hasClinicianRole) {
            next({ name: 'Dashboard', params: { dashboardType: 'clinician' } });
            return;
          }
          next({ name: 'Home' });
          return;
        }
      }

      if (dashboardType === 'clinician') {
        if (!authStore.hasAdminRole && !authStore.hasClinicianRole) {
          if (authStore.hasResearcherRole) {
            next({ name: 'Dashboard', params: { dashboardType: 'study' } });
            return;
          }
          next({ name: 'Home' });
          return;
        }
      }
    }
    next();
  } else {
    next();
  }
});

export default router;
