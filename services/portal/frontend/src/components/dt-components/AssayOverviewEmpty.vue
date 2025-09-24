<template>
  <v-container class="text-center py-16 px-4 no-select assay-overview-empty" fluid>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <h2 class="title font-weight-bold mb-4 focus-in-expand">
          Oops! It seems this assay is not ready to launch.
        </h2>
        <p class="text-white text-opacity-80 mb-8">
          Please double-check that the workflow, datasets, and cohorts are set up correctly. If the issue continues, kindly reach out to your system administrator for assistance.
        </p>
        <div class="d-flex justify-center flex-wrap gap-4">
            <div class="roll-in-left">
                <v-btn 
                    variant="tonal"
                    class="hover-animate heartbeat"
                    size="80"
                    @click="$router.back()"
                    >
                    <v-icon 
                        icon="mdi-arrow-left" 
                        size="30"
                        color="cyan-darken-2"
                    >
                    </v-icon>
                </v-btn>
            </div>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts" setup>
</script>

<style scoped>
.assay-overview-empty{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}
.title{
    font-size: 3.5rem;
    line-height: 1.2;
}
.text-opacity-80 {
    opacity: 0.8;
}

.gap-4 {
    gap: 1rem;
}
.no-select{
    user-select: none;
    -webkit-user-select: none; /* Safari */
}


</style>
