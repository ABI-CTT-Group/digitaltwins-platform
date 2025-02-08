import { defineStore } from "pinia";
import { ref } from "vue";
import * as Copper from "copper3d"

interface IUser {
  name: string;
  role: string;
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