<template>
    <div class="fill-height d-flex flex-column justify-center align-center">
        <div class="h-70">
            <div class="mx-5 my-10 text-center">
                <h1 class="text-h2 title">DigitalTWINS Portal</h1>
            </div>
            <div class="mx-auto rounded w-66 form-login">
                <v-form validate-on="submit lazy" @submit.prevent="submit">
                    <v-text-field
                        v-model="userName"
                        :rules="rulesUser"
                        label="Username"
                    ></v-text-field>
                    <v-text-field
                        v-model="password"
                        :rules="rulesPassword"
                        type="password"
                        label="Password"
                    ></v-text-field>
                    <v-btn
                        :loading="loading"
                        class="mt-2"
                        text="Sign in"
                        type="submit"
                        color="#009688"
                        block
                    ></v-btn>
                </v-form>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUser } from "@/plugins/hooks/user";

const publicData = {
    user1: {
        userName: 'participant_1',
        password: '123456',
        role: 'clinician'
    },
    user2: {
        userName: 'researcher_1',
        password: '123456',
        role: 'researcher'
    },
    admin: {
        userName: 'admin',
        password: 'admin',
        role: 'admin'
    }
}

const userName = ref('');
const role = ref('');
const password = ref('');
const loading = ref(false);
const rulesUser = [(value:string) => checkApi(value, 'userName')];
const rulesPassword = [(value:string) => checkApi(value, 'password')];
const timeout = ref<null|NodeJS.Timeout>(null);
const router = useRouter();
const isUser = ref(false);
const { setUser } = useUser();

const submit = async (event:any) => {
        loading.value = true
        const results = await event
        loading.value = false
        if (results.valid === true){
            switch (userName.value) {
                case "admin":
                    router.push({name: 'Home'})
                    break;
                default:

                    router.push({name: 'Home'})
                    break;
            }
            setUser(userName.value, role.value);
        }
      }

const checkApi = async (validatingStr: string, type: string): Promise<any> => {
    return new Promise(resolve => {
        clearTimeout(timeout.value as NodeJS.Timeout);
        
        timeout.value = setTimeout(() => {
            if (type === 'userName'){
                if (!validatingStr) return resolve('Please enter a user name.')
                if (validatingStr === publicData.user1.userName || validatingStr === publicData.admin.userName){
                    isUser.value = true;
                    return resolve(true);
                }else{
                    isUser.value = false;
                    return resolve('User does not exist.')
                }
            }else if(type === 'password'){
                if (!validatingStr) return resolve('Please enter a password.')
                if (isUser.value){
              
                    switch (userName.value) {
                        case publicData.user1.userName:
                            if (validatingStr === publicData.user1.password) {
                                role.value = publicData.user1.role;
                                return resolve(true)
                            }
                            break;
                        case publicData.user2.userName:
                            if (validatingStr === publicData.user1.password) {
                                role.value = publicData.user2.role;
                                return resolve(true);
                            }
                            
                            break;
                        case publicData.admin.userName:
                            if (validatingStr === publicData.admin.password) {
                                role.value = publicData.admin.role;
                                return resolve(true);
                            }
                            break;
                    }
                    return resolve('Password is incorrect.')
                }
            }else{
                return resolve(false)
            }
            return resolve(true)
        }, 1000)
    })
}
</script>

<style scoped>
.form-login{
    min-width: 30rem;
}
.title{
    font-family: "Poppins", "Helvetica Neue", Arial, sans-serif; 
    line-height: 1.6; 
    color: #F5F5F5; 
}
</style>