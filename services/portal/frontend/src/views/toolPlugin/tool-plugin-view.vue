<template>
    <!-- <div class="exit balloon heartbeat gradient-animated" onclick="window.history.back()"></div> -->
    <div class="exit d-flex justify-center flex-wrap gap-4">
            <div class="roll-in-left">
                <v-btn 
                    variant="tonal"
                    class="hover-animate heartbeat btn"
                    size="60"
                    @click="$router.back()"
                    >
                    <v-icon 
                        class="icon"
                        icon="mdi-exit-to-app" 
                        size="25"
                        color="deep-orange"
                    >
                    </v-icon>
                </v-btn>
            </div>
        </div>
    <div >
        <remote-component-app :src="remoteApp.path" :expose="remoteApp.expose" />
    </div>
</template>

<script setup lang="ts">
import RemoteComponentApp from '@/components/RemoteComponentApp.vue';
import { useRemoteAppStore } from '@/store/remoteStore';

const {remoteApp} = useRemoteAppStore()

</script>

<style scoped>
.exit{
    position: fixed;
    top: 10px;
    left: 50%;
    z-index: 99999;
}
.icon {
    transform: rotate(-180deg);
}
/* .btn {
    background-color: rgba(255,255,255, 0.2);
} */

</style>