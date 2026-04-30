<template>
    <div class="container overflow-hidden d-flex justify-center">
        <div class="overflow-y-auto sub-container">
            <Hero >
                 <v-btn
                    color="green-lighten-2"
                    class="text-sky-900 px-6 py-3"
                    size="large"
                    elevation="6"
                    rounded="xl"
                    variant="tonal"
                    @click="handleHeroStarted"
                >
                    Get Started
                </v-btn>
                <v-btn
                    color="purple-lighten-2"
                    class="text-white px-6 py-3"
                    size="large"
                    elevation="6"
                    rounded="xl"
                    variant="tonal"
                    @click="handleHeroDocumentation"
                >
                    Documentation
                </v-btn>
            </Hero>
            <v-row class="cards">
                <v-col
                    v-for="(card, i) in cards"
                    :key="i"
                    cols="12"
                    md="4"
                    class="d-flex justify-center align-center mb-4"
                >
                    <DashboardCard 
                        :src="card.image" 
                        :title="card.title"
                        :location="card.location"
                        :description="card.description"
                        @on-explore="() => dispatch(card)"
                    />
                </v-col>
            </v-row>
        </div>
    </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import DashboardCard from '@/components/domain/DashboardCard.vue';
import Hero from '@/components/domain/Hero.vue';
import { useRouter } from 'vue-router';
import { useAuthGuard } from '@/composables/useAuthGuard';
import { cards, CardConfig } from './home.cards';

const router = useRouter();
const { check } = useAuthGuard();

onMounted(() => {
    sessionStorage.removeItem("dashboardPage");
});

const dispatch = (card: CardConfig) => {
    if (!check(card.requireRoles)) return;

    if (card.action?.type === 'route') {
        router.push({ name: card.action.name, params: card.action.params });
    } else if (card.action?.type === 'external') {
        window.open(card.action.url, '_blank');
    }
}

const handleHeroStarted = () => {
     router.push({ name: 'ClinicianDashboard' });
}

const handleHeroDocumentation = () => {
    router.push({name:'TutorialDashboard'});
}
</script>

<style scoped>
.sub-container{
    width: 90%;
    margin-top: 70px;
}
</style>