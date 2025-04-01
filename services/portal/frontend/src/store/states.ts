import { defineStore } from "pinia";
import { ref } from "vue";
import * as Copper from "copper3d";
import { IDashboardCategory, IAssayDetails } from "@/models/apiTypes";

interface IUser {
  name: string;
  role: string;
}
interface IAllAssayDetailsOfStudy {
  [key: string]: IAssayDetails;
}
interface IAssayBtnText {
  [key: string]: {text:string, url:string};
}

export const currentUserStore = defineStore("currentUser", () => {
    const user = ref<IUser>();
    const setUser = (username:string, role:string) => {

      user.value = {
        name: username,
        role: role
      }
    };
    return {
      user,
      setUser,
    };
  });

export const useDashboardPageStore = defineStore("dashboardPage", () => {
  const currentCategory = ref("");
  const breadCrumbsCategory = ref("");
  const exploredCard = ref<{category:string, data:IDashboardCategory[]}[]>([]);
  const currentCategoryData = ref<IDashboardCategory[]>([]);
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
  const currentAssayDetails = ref<IAssayDetails>();
  const allAssayDetailsOfStudy = ref<IAllAssayDetailsOfStudy>({});
  const assayExecute = ref<IAssayBtnText>();
  const isClinicianView = ref<boolean>(false);

  const setCurrentCategory = (category:string) => {
    currentCategory.value = category;
  };
  const setBreadCrumbsCategory = (category:string) => {
    breadCrumbsCategory.value = category;
  }
  const setExploredCard = (category:string, data:IDashboardCategory[]) => {
    exploredCard.value.push({category:category, data:data});
  }
  const setCurrentCategoryData = (data:IDashboardCategory[]) => {
    currentCategoryData.value = data;
  }
  const setBreadCrumbsItems = (item:{title:string, disabled:boolean}) => {
    breadCrumbsItems.value.push(item);
  }
  const setDetailsRenderItems = (categories:{category: string, name: string, description: string}[], description:string) => {
    detailsRenderItems.value.categories = categories;
    detailsRenderItems.value.description = description;
  }
  const setCurrentAssayDetails = (assayDetails:IAssayDetails) => {
    currentAssayDetails.value = assayDetails;
  }
  const setAllAssayDetailsOfStudy = (uuid:string, assayDetails:IAssayDetails) => {
    allAssayDetailsOfStudy.value![uuid] = assayDetails;
  }
  const setAssayExecute = (uuid:string, btnText:string, url:string) => {
    assayExecute.value![uuid] = {
      text: btnText,
      url: url,
    };
  }
  const setClinicianView = (state:boolean) => {
    isClinicianView.value = state;
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
    isClinicianView,
    setCurrentCategory,
    setBreadCrumbsCategory,
    setExploredCard,
    setCurrentCategoryData,
    setBreadCrumbsItems,
    setDetailsRenderItems,
    setAllAssayDetailsOfStudy,
    setCurrentAssayDetails,
    setAssayExecute,
    setClinicianView
  }

});