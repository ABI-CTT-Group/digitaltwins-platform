import { defineStore } from "pinia";
import { ref } from "vue";
import { DashboardCategory, AssayDetails } from "@/models/types";

interface IAllAssayDetailsOfStudy {
  [key: string]: AssayDetails;
}
interface IAssayBtnText {
  [key: string]: {text:string, url:string, isLaunching?: boolean};
}

export const useDashboardPageStore = defineStore("dashboardPage", () => {
  const currentCategory = ref("");
  const breadCrumbsCategory = ref("");
  const exploredCard = ref<{category:string, data:DashboardCategory[]}[]>([]);
  const currentCategoryData = ref<DashboardCategory[]>([]);
  const breadCrumbsItems = ref([
      { title: 'Programmes', disabled: false },
  ]);
  const detailsRenderItems = ref<{
    categories: {category: string, name: string, description: string}[];
    description: string;
  }>({
    categories:[],
    description: "",
  });
  const currentAssayDetails = ref<AssayDetails>();
  const allAssayDetailsOfStudy = ref<IAllAssayDetailsOfStudy>({});
  const assayExecute = ref<IAssayBtnText>();

  const setCurrentCategory = (category:string) => {
    currentCategory.value = category;
  };
  const setBreadCrumbsCategory = (category:string) => {
    breadCrumbsCategory.value = category;
  }
  const setExploredCard = (category:string, data:DashboardCategory[]) => {
    exploredCard.value.push({category:category, data:data});
  }
  const setCurrentCategoryData = (data:DashboardCategory[]) => {
    currentCategoryData.value = data;
  }
  const setBreadCrumbsItems = (item:{title:string, disabled:boolean}) => {
    breadCrumbsItems.value.push(item);
  }
  const setDetailsRenderItems = (categories:{category: string, name: string, description: string}[], description:string) => {
    detailsRenderItems.value.categories = categories;
    detailsRenderItems.value.description = description;
  }
  const setCurrentAssayDetails = (assayDetails:AssayDetails) => {
    currentAssayDetails.value = assayDetails;
  }
  const setAllAssayDetailsOfStudy = (uuid:string, assayDetails:AssayDetails) => {
    allAssayDetailsOfStudy.value![uuid] = assayDetails;
  }
  const setAssayExecute = (uuid:string, btnText:string, url:string) => {
    assayExecute.value![uuid] = {
      text: btnText,
      url: url,
    };
  }
  const setAssayLaunching = (uuid: string, isLaunching: boolean) => {
    if (assayExecute.value![uuid]) {
      assayExecute.value![uuid].isLaunching = isLaunching;
    }
  }
  return {
    currentCategory,
    breadCrumbsCategory,
    exploredCard,
    currentCategoryData,
    breadCrumbsItems,
    detailsRenderItems,
    allAssayDetailsOfStudy,
    currentAssayDetails,
    assayExecute,
    setCurrentCategory,
    setBreadCrumbsCategory,
    setExploredCard,
    setCurrentCategoryData,
    setBreadCrumbsItems,
    setDetailsRenderItems,
    setAllAssayDetailsOfStudy,
    setCurrentAssayDetails,
    setAssayExecute,
    setAssayLaunching,
  }
}, {
  persist: {
    pick: ['breadCrumbsItems', 'currentCategory', 'exploredCard'],
    storage: sessionStorage,
  }
});