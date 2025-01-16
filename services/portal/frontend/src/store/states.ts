import { defineStore } from "pinia";
import { ref } from "vue";
import * as Copper from "copper3d"

export const currentUserStore = defineStore("currentUser", () => {
    const user = ref<string>();
    const setUser = (username:string) => {

      user.value = username;
    };
    return {
      user,
      setUser,
    };
  });

// time consuming operation
// export const useNrrdToolsStore = defineStore("nrrdTools", () => {
//     const nrrdTools = ref<Copper.NrrdTools>();
//     const setNrrdTools = (tool:Copper.NrrdTools) => {
//       nrrdTools.value = tool;
//     };
//     return {
//       nrrdTools,
//       setNrrdTools,
//     };
//   });