import {currentUserStore} from "@/store/states";
import { storeToRefs } from "pinia";

export function encryptKey(passkey: string) {
  return btoa(passkey);
}

export function decryptKey(passkey: string) {
return atob(passkey);
}

export const useUser = () => {
  const { setUser } = currentUserStore();
  const { user } = storeToRefs(currentUserStore());
  if (!!user.value) {
    localStorage.setItem('tumourAppRole', encryptKey(encryptKey(user.value.role) + '-'+ Date.now()));
  }else{
    // try to get the user from local storage
    const localData = typeof window !== "undefined" ? window.localStorage.getItem('tumourAppRole') : null;
    if(!!localData){
      const decryptedData = decryptKey(localData);
      const [encryptRole, timestamp] = decryptedData.split('-');
      const role = decryptKey(encryptRole);
      if(role === 'admin'){
          const diff = Date.now() - parseInt(timestamp);
          if(diff < 1000 * 60 * 60){
              setUser(role, role);
          }else{
              localStorage.removeItem('accessKey');
          }
      }
  }
  }

  return { user, setUser };
};