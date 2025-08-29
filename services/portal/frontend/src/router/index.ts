// Composables
import {
  createRouter,
  createWebHistory,
  createWebHashHistory,
} from "vue-router";
import Login from "@/views/index.vue";
import Home from "@/views/dashboard/index.vue";
import Dashboard from "@/views/dashboard/study-dashboard/index.vue";
import TutorialDashboard from "@/views/dashboard/tutorial-dashboard/index.vue";
import CatalogueDashboard from "@/views/dashboard/catalogue-dashboard/index.vue";
import CatalogueDashboardView from "@/views/dashboard/catalogue-dashboard/catalogue-dashboard-view.vue";
import WorkflowToolsViewer from "@/views/dashboard/catalogue-dashboard/workflow-tools-viewer.vue";
import Layout from "@/layouts/Default.vue";
import LaunchedAssayOverview from "@/views/dashboard/study-dashboard/assay-overview.vue";
const routes = [
  {
    path: "/",
    name: "Login",
    component: Login,
  },
  {
    path:"/home",
    component: Layout,
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
            // props: (route:any) => ({ dashboardType: route.params.dashboardType })
          },
          {
            path: "/how-it-works",
            name: "TutorialDashboard",
            component:TutorialDashboard
          },
          {
            path: "/catalogue-dashboard",
            component:CatalogueDashboard,
            children:[
              {
                path: "/catalogue-dashboard",
                name: "CatalogueDashboardView",
                component: CatalogueDashboardView,
              },
              {
                path: "/catalogue-dashboard-workflow-tools",
                name: "WorkflowToolsViewer",
                component: WorkflowToolsViewer,
              }
            ]
          },
          {
            path: "/launched-assay",
            name: "LaunchedAssayOverview",
            component: LaunchedAssayOverview,
          }
    ]
  },

];


// use for the github repo

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

// export default router;

// const router = createRouter({
//   history: createWebHashHistory(),
//   linkActiveClass: "active",
//   routes,
// });
// export default router;

// console.log(process.env.BASE_URL);

// const router = createRouter({
//   history: createWebHistory(),
//   routes,
// });

export default router;
