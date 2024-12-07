import { defineStore } from "pinia";
import { ref } from "vue";
import {
    useTumourPositionStudyDetails,
    useStudyDisplayNrrd
} from "@/plugins/tumour_position_study_api";
import { ITumourStudyAppDetails, ITumourStudyReport } from "@/models/apiTypes";

export const useTumourStudyDetailsStore = defineStore("TumourStudyDetails", () => {
    const studyDetails = ref<ITumourStudyAppDetails>();
    const getTumourStudyDetails = async () => {
        studyDetails.value = await useTumourPositionStudyDetails();
    };
    return {
        studyDetails,
        getTumourStudyDetails,
    };
});

export const useTumourStudyNrrdStore = defineStore("getTumourStudyNrrd", () => {
    const studyNrrd = ref<string>();
    const getStudyNrrd = async (filepath: string) => {
        studyNrrd.value = (await useStudyDisplayNrrd(filepath)) as string;
    };
    return {
        studyNrrd,
        getStudyNrrd,
    };
  });
