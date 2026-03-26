// Composables
import {
  createRouter,
  createWebHistory,
  createWebHashHistory,
  RouteRecordRaw,
} from "vue-router";
import { useAuthStore } from "@/store/auth_store";
import { isAuthenticated } from "@/plugins/keycloak";
import Login from "@/views/index.vue";
import Home from "@/views/dashboard/index.vue";
import Dashboard from "@/views/dashboard/study-dashboard/index.vue";
import TutorialDashboard from "@/views/dashboard/tutorial-dashboard/index.vue";
import CatalogueDashboard from "@/views/dashboard/catalogue-dashboard/index.vue";
import CatalogueDashboardView from "@/views/dashboard/catalogue-dashboard/catalogue-dashboard-view.vue";
import ToolsViewer from "@/views/dashboard/catalogue-dashboard/tools-viewer.vue";
import Layout from "@/layouts/Default.vue";
import LaunchedAssayOverview from "@/views/dashboard/study-dashboard/assay-overview.vue";
import UploadDataset from "@/views/upload-dataset/index.vue";
import UploadToolDataset from "@/views/upload-dataset/workflow-tool/index.vue";
import UploadWorkflowDataset from "@/views/upload-dataset/workflow/index.vue";
import PluginHome from "@/views/toolPlugin/index.vue";
import ToolPluginView from "@/views/toolPlugin/tool-plugin-view.vue";


const routes = [
  {
    path: "/",
    name: "Login",
    component: Login,
  },
  {
    path:"/home",
    component: Layout,
    meta: { requiresAuth: true },
    children:[
          {
            path: "/home",
            name: "Home",
            component: Home,
          },
          {
            path: "/dashboard:dashboardType",
            name: "Dashboard",
            component: Dashboard,
            meta: { requiresAuth: true },
          },
          {
            path: "/how-it-works",
            name: "TutorialDashboard",
            component:TutorialDashboard,
            meta: { requiresAuth: true },
          },
          {
            path: "/catalogue-dashboard",
            component:CatalogueDashboard,
            meta: { requiresAuth: true },
            children:[
              {
                path: "/catalogue-dashboard",
                name: "CatalogueDashboardView",
                component: CatalogueDashboardView,
              },
              {
                path: "/catalogue-dashboard-tools",
                name: "ToolsViewer",
                component: ToolsViewer,
              }
            ]
          },
          {
            path: "/launched-assay",
            name: "LaunchedAssayOverview",
            component: LaunchedAssayOverview,
            meta: { requiresAuth: true },
          },
          {
            path: "/upload-dataset",
            name: "UploadDataset",
            component: UploadDataset,
            meta: { requiresAuth: true },
            children:[
              {
                path: "/upload-tool-dataset",
                name: "UploadToolDataset",
                component: UploadToolDataset,
              },
              {
                path: "/upload-workflow-dataset",
                name: "UploadWorkflowDataset",
                component: UploadWorkflowDataset,
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
  const requiresAuth = to.meta?.requiresAuth;
  const hasToken = !!sessionStorage.getItem('access_token');

  // Update auth state in case token was updated
  authStore.updateAuthState();

  if (requiresAuth) {
    if (!isAuthenticated() && !hasToken) {
      // Redirect to login if not authenticated
      next({ name: 'Login' });
    } else {
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
    }
  } else {
    next();
  }
});

export default router;
