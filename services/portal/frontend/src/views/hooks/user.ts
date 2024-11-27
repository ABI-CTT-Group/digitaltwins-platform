import {currentUserStore} from "@/store/states";
import { storeToRefs } from "pinia";


export const useUser = () => {
  const { setUser } = currentUserStore();
  const { user } = storeToRefs(currentUserStore());
  return { user, setUser };
};