import { defineStore } from "pinia";
import { ref } from "vue";

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