// Composables
import {
  createRouter,
  createWebHistory,
  createWebHashHistory,
} from "vue-router";
import Login from "@/views/index.vue";
import Dashboard from "@/views/dashboard/index.vue";
import ManuallyTumourSegmentation from "@/views/tumour-segmentation-manually/MainPage.vue";
import ManuallyTumourCalculation from "@/views/tumour-distance-calculation/MainPage.vue";
import ManuallyTumourCenter from "@/views/tumour-center-manually/MainPage.vue";
import ManuallyTumourAssisted from "@/views/tumour-assisted-manually/MainPage.vue";
import SegmentationLayout from "@/layouts/segmentation-layout/Default.vue";
import CalculationLayout from "@/layouts/calculation-layout/Default.vue";

const routes = [
  {
    path: "/",
    name: "Login",
    component: Login,
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: Dashboard,
  },
  {
    path: "/tumour-segmentation-manual",
    component: SegmentationLayout,
    children: [
      {
        path: "/tumour-segmentation-manual",
        name: "TumourSegmentationStudy",
        // route level code-splitting
        // this generates a separate chunk (about.[hash].js) for this route
        // which is lazy-loaded when the route is visited.
        component: ManuallyTumourSegmentation,
      },
    ],
  },
  {
    path: "/tumour-calculation-manual",
    component: CalculationLayout,
    children: [
      {
        path: "/tumour-calculation-manual",
        name: "TumourCalaulationStudy",
        component: ManuallyTumourCalculation,
      },
    ],
  },
  {
    path: "/tumour-center-manual",
    component: CalculationLayout,
    children: [
      {
        path: "/tumour-center-manual",
        name: "TumourCenterStudy",
        component: ManuallyTumourCenter,
      },
    ],
  },
  {
    path: "/tumour-assisted-manual",
    component: CalculationLayout,
    children: [
      {
        path: "/tumour-assisted-manual",
        name: "TumourAssistedStudy",
        component: ManuallyTumourAssisted,
      },
    ],
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
