// Composables
import {
  createRouter,
  createWebHistory,
  createWebHashHistory,
} from "vue-router";
import Login from "@/views/index.vue";
import Dashboard from "@/views/dashboard/index.vue";
import ManuallyTumourSegmentation from "@/views/tumour-segmentation-manually/MainPage.vue";

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
    path: "/tumour-manual",
    component: () => import("@/layouts/default/Default.vue"),
    children: [
      {
        path: "/tumour-manual",
        name: "MainPage",
        // route level code-splitting
        // this generates a separate chunk (about.[hash].js) for this route
        // which is lazy-loaded when the route is visited.
        component: ManuallyTumourSegmentation,
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
