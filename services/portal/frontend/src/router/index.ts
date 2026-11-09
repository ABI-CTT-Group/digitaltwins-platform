// Composables
import {
  createRouter,
  createWebHistory,
  type RouteLocationNormalized,
} from "vue-router";
import { useAuthStore } from "@/store/auth_store";
import { isAuthenticated } from "@/bootstrap/keycloak";
import Home from "@/views/home/index.vue";
import DashboardView from "@/views/dashboard/DashboardView.vue";
import TutorialDashboard from "@/views/tutorial/index.vue";
import CatalogueDashboardView from "@/views/catalogue/catalogue-dashboard-view.vue";
import ToolsViewer from "@/views/catalogue/tools-viewer.vue";
import IsaProjectHub from "@/views/isa-project/IsaProjectHub.vue";
import Layout from "@/layouts/Default.vue";
import LaunchedAssayOverview from "@/views/dashboard/report/AssayReportView.vue";
import UploadDataset from "@/views/upload-dataset/index.vue";
import UploadToolDataset from "@/views/upload-dataset/workflow-tool/index.vue";
import UploadWorkflowDataset from "@/views/upload-dataset/workflow/index.vue";
import UploadMeasurementsDataset from "@/views/upload-dataset/measurements/index.vue";
import MeasurementFhirPreview from "@/views/upload-dataset/measurements/MeasurementFhirPreview.vue";
import UploadModelDataset from "@/views/upload-dataset/models/index.vue";
import ToolsOverallView from "@/views/upload-dataset/workflow-tool/ToolsOverallView.vue";
import WorkflowsOverallView from "@/views/upload-dataset/workflow/WorkflowsOverallView.vue";
import MeasurementsOverallView from "@/views/upload-dataset/measurements/MeasurementsOverallView.vue";
import ModelsOverallView from "@/views/upload-dataset/models/ModelsOverallView.vue";
import RegisterWizard from "@/views/upload-dataset/components/RegisterWizard.vue";
import UploadMeasurementForm from "@/views/upload-dataset/measurements/UploadMeasurementForm.vue";
import UploadModelForm from "@/views/upload-dataset/models/UploadModelForm.vue";

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
            path: "/study-dashboard",
            name: "StudyDashboard",
            component: DashboardView,
            meta: { requiresAuth: true, requiresRoles: ['admin', 'researcher'], type: 'study' },
          },
          {
            path: "/clinician-dashboard",
            name: "ClinicianDashboard",
            component: DashboardView,
            meta: { requiresAuth: true, requiresRoles: ['admin', 'researcher', 'clinician'], type: 'clinician' },
          },
          {
            path: "/how-it-works",
            name: "TutorialDashboard",
            component: TutorialDashboard,
          },
          {
            path: "/catalogue",
            name: "CatalogueDashboardView",
            component: CatalogueDashboardView,
          },
          {
            path: "/catalogue/workflow-assembler",
            name: "ToolsViewer",
            component: ToolsViewer,
            meta: { requiresAuth: true },
          },
          {
            // Frontend-only prototype: ISA projects live in the browser; nothing reaches the API.
            path: "/catalogue/isa-project",
            name: "IsaProjectPrototype",
            component: IsaProjectHub,
            meta: { requiresAuth: true, requiresRoles: ['admin'] },
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
            redirect: { name: "CatalogueDashboardView" },
            meta: { requiresAuth: true },
            children:[
              // Each hub is a layout: its list, a new item's wizard, and an existing item's wizard at a step
              // (views/upload-dataset/components/registrationSteps.ts). Roles sit on the hub and cover all three.
              {
                path: "/catalogue/tools",
                component: UploadToolDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin'] },
                children: [
                  { path: "", name: "UploadToolDataset", component: ToolsOverallView },
                  { path: "new", name: "RegisterTool", component: RegisterWizard, props: { type: "tool" } },
                  { path: ":id/register", name: "ContinueToolRegistration", component: RegisterWizard,
                    props: (r: RouteLocationNormalized) => ({ type: "tool", id: r.params.id }) },
                ],
              },
              {
                path: "/catalogue/workflows",
                component: UploadWorkflowDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin'] },
                children: [
                  { path: "", name: "UploadWorkflowDataset", component: WorkflowsOverallView },
                  { path: "new", name: "RegisterWorkflow", component: RegisterWizard, props: { type: "workflow" } },
                  { path: ":id/register", name: "ContinueWorkflowRegistration", component: RegisterWizard,
                    props: (r: RouteLocationNormalized) => ({ type: "workflow", id: r.params.id }) },
                ],
              },
              {
                path: "/catalogue/measurements",
                component: UploadMeasurementsDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin', 'researcher'] },
                children: [
                  { path: "", name: "UploadMeasurementsDataset", component: MeasurementsOverallView },
                  { path: "new", name: "RegisterMeasurement", component: UploadMeasurementForm },
                  { path: ":id/register", name: "ContinueMeasurementRegistration", component: UploadMeasurementForm, props: true },
                ],
              },
              {
                path: "/catalogue/models",
                component: UploadModelDataset,
                meta: { requiresAuth: true, requiresRoles: ['admin', 'researcher'] },
                children: [
                  { path: "", name: "UploadModelDataset", component: ModelsOverallView },
                  { path: "new", name: "RegisterModel", component: UploadModelForm },
                  { path: ":id/register", name: "ContinueModelRegistration", component: UploadModelForm, props: true },
                ],
              },
              {
                path: "/catalogue/measurements/:id/preview",
                name: "MeasurementFhirPreview",
                component: MeasurementFhirPreview,
                meta: { requiresAuth: true, requiresRoles: ['admin', 'researcher'] },
              },
            ]
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
  authStore.updateAuthState();

  if (requiresAuth) {
    // Keycloak is the only source of truth. (There used to be a sessionStorage
    // `access_token` fallback here, but nothing ever wrote that key.)
    if (!isAuthenticated()) {
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

    next();
  } else {
    next();
  }
});

export default router;
