<template>
    <div class="w-100 flex-grow-1 d-flex flex-column justify-center align-center no-data">
        <v-icon size="64" color="#5fd6e8">mdi-database-off-outline</v-icon>
        <h2 class="mt-4">No data available</h2>
        <p>
            It seems there is nothing to display here. Try refreshing or check back later.
        </p>
    </div>
</template>

<style scoped>
.no-data { font-family: "Nunito", sans-serif; }
.no-data h2 { color: #e9f2f5; font-weight: 600; }
.no-data p { color: #7f97a1; }
</style>
